"""
节点管理器    
- 实现功能  
    1.清理端口  
    2.获取可用端口  
    3.获取正在运行的端口  
    4.随机化生成节点meta数据 
    5.启动端口，发布start消息  
    6.定时检查端口状态，如果所有端口运行完毕，发布结束消息  
"""
# 库
import math
import yaml
import time
import json
import socket
import requests
import random
import copy
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any, Tuple

# 组件
from src.manager.service.message import (
    Message,
    StartMessage,StartMessagePayload,
    WaitingMessage,WaitingPayload,
    ShutdownMessage,ShutdownPayload
)
from src.manager.database import get_code_list, read_db_to_get_code_list
from src.manager.service.bus import MESSAGE_BUS
from src.manager.redis import REDIS_CONNECTOR, REDIS_PREFIX_MANAGER
from src.utils.warn.deprecate import deprecated

# 日志
from src.utils.logger import get_module_logger
from src.utils.thread import interruptible_sleep
logger = get_module_logger(__name__,'[NodeManager]')

class NodeManager:
    def __init__(self):
        # 配置
        self._node_config = {}
        self._meta_param = {}
        self._meta_seed = None
        self._shutdown_confirm_count = 3  # 默认值

        # 线程管理
        self.monitor_started = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_lock = threading.Lock()

        # 等待节点完成相关
        self.waiting_for_nodes = False
        self._waiting_thread: Optional[threading.Thread] = None
        self._waiting_lock = threading.Lock()

        # Redis 客户端
        self._redis_client = REDIS_CONNECTOR.get_client()

        # 加载配置
        self._load_config()

        # 注册消息处理器
        self._subscribe()

    def _load_config(self):
        """加载配置：node.yaml 为节点/端口配置，hyparam.yaml 为 meta 配置（stock_pool 由 code_list 读取）。"""
        try:
            with open('src/config/node.yaml', 'r', encoding='utf-8') as f:
                self._node_config = yaml.safe_load(f) or {}
            with open('src/config/hyparam.yaml', 'r', encoding='utf-8') as f:
                hyparam = yaml.safe_load(f) or {}
            self._meta_param = hyparam.get('meta', {})
            self._meta_seed = hyparam.get('meta_seed', None)
            self._shutdown_confirm_count = hyparam.get('shutdown_confirm', {}).get('count', 3)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise 
    
    # ============================ 清理端口 ============================
    def clear_ports(self) -> bool:
        """清空端口池：调用微服务 DELETE /clear，将所有已分配端口移回可用队列。"""
        host = self._node_config.get('web',{}).get('ms_clear_host', '43.139.192.176')
        port = self._node_config.get('web',{}).get('ms_clear_port', 8190)
        base = f"http://{host}:{port}"
        url = self._node_config.get('web',{}).get('ms_clear_url', '/clear')

        try:
            response = requests.delete(base + url, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"清空端口请求失败: {e}")
            return False

    # ============================ 查询节点状态接口 ============================
    def _get_single_node_status(
        self,
        host: str,
        port: int,
        connect_timeout: float = None
    ) -> Optional[Dict[str, Any]]:
        """
        查询单个节点状态（基础方法）
        
        通过 TCP 连接发送 {"req": 0} 查询节点状态，返回完整的状态字典。
        
        Args:
            host: 节点主机地址
            port: 节点端口
            connect_timeout: 连接超时时间（秒），默认从配置读取
        
        Returns:
            Optional[Dict[str, Any]]: 节点状态字典，包含：
                - running: int (0/1) 是否正在运行
                - current_year_month: List[int] 或 Tuple[int, int] 当前窗口(year, month)
                - pid: int 进程号
                - node_id: str 节点id (从 frp 状态文件中获取)
            如果连接失败、超时或解析失败，返回 None
        """
        if connect_timeout is None:
            web = self._node_config.get('web', {})
            connect_timeout = float(web.get('timeout', 2.0))
        
        payload = json.dumps({"req": 0}).encode('utf-8')
        sock = None
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)
            sock.connect((host, port))
            sock.sendall(payload)
            sock.settimeout(connect_timeout)
            
            # 接收响应数据
            data = sock.recv(4096).decode('utf-8', errors='replace').strip()
            if not data:
                return None
            
            # 解析 JSON
            status = json.loads(data)
            if not isinstance(status, dict):
                return None
            
            return status
            
        except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError, OSError):
            return None
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
    
    def get_all_status(self) -> Dict[int, Dict[str, Any]]:
        """
        获取所有节点的完整状态
        
        Returns:
            Dict[int, Dict[str, Any]]: 端口到状态字典的映射
                键为端口号，值为节点状态字典（包含 running, current_year_month, pid, node_id）
                如果节点不可用，则不会出现在字典中
        """
        web = self._node_config.get('web', {})
        host = web.get('node_host', 'localhost')
        pr = web.get('port_range', [8191, 8220])
        start_port = int(pr[0])
        end_port = int(pr[1])
        connect_timeout = float(web.get('timeout', 2.0))
        max_workers = min(end_port - start_port + 1, web.get('max_worker', 32))
        
        all_status: Dict[int, Dict[str, Any]] = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._get_single_node_status, host, port, connect_timeout): port
                for port in range(start_port, end_port + 1)
            }
            for future in as_completed(futures):
                try:
                    status = future.result()
                    port = futures.get(future)
                    if status is not None:
                        all_status[port] = status
                except Exception:
                    port = futures.get(future)
                    pass  # 单端口异常不逐条打日志，下面统一汇总
        failed_ports = set(range(start_port, end_port + 1)) - set(all_status.keys())
        if failed_ports:
            logger.debug(f"以下 {len(failed_ports)} 个端口不可用: {sorted(failed_ports)}")
        logger.info(f"成功查询 {len(all_status)} 个节点的状态")
        return all_status

    def get_all_available_port(self) -> List[str]:
        """
        获取所有可用端口（能连接且返回合法状态）
        
        Returns:
            List[str]: 可用端口列表（字符串格式）
        """
        all_status = self.get_all_status()
        available_ports = [str(port) for port in sorted(all_status.keys())]
        logger.info(f"可用端口数: {len(available_ports)}, 端口: {available_ports}")
        return available_ports

    def _get_port_range(self) -> Tuple[int, int, int]:
        """从配置读取端口范围，返回 (start_port, end_port, port_count)。"""
        web = self._node_config.get('web', {})
        pr = web.get('port_range', [8191, 8220])
        start_port = int(pr[0])
        end_port = int(pr[1])
        port_count = end_port - start_port + 1
        return start_port, end_port, port_count

    def get_all_running_task_port(self, task_id: str) -> List[str]:
        """
        获取运行指定 task_id 的所有端口
        
        Args:
            task_id: 任务ID
        
        Returns:
            List[str]: 运行指定 task_id 的端口列表（字符串格式）
        """
        all_status = self.get_all_status()
        running_ports: List[str] = []
        
        for port, status in all_status.items():
            # 检查是否在运行
            if status.get('running') == 1:
                # 如果状态中包含 task_id，可以进一步过滤
                # 如果状态中没有 task_id，则所有 running==1 的节点都返回
                # 根据实际需求调整
                status_task_id = status.get('task_id')
                if status_task_id is None or status_task_id == task_id:
                    running_ports.append(str(port))
        
        running_ports.sort(key=int)  # 按端口号排序
        logger.info(f"运行 task_id={task_id} 的端口数: {len(running_ports)}, 端口: {running_ports}")
        return running_ports 

    # ============================ 随机化生成节点meta数据 ============================
    def _parse_earliest_year_month(self, val: Any) -> Tuple[int, int]:
        """解析 earliest_year_month：支持 [y,m]、'(y, m)' 或 (y,m)。"""
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            return (int(val[0]), int(val[1]))
        if isinstance(val, str):
            s = val.strip(' ()')
            parts = s.split(',')
            if len(parts) >= 2:
                return (int(parts[0].strip()), int(parts[1].strip()))
        return (1997, 1)

    def _sample_model_config_by_cate(self, model_cfg: Dict[str, Any], cate: int, rng: random.Random) -> Dict[str, Any]:
        """按 cate 从 hyparam 的 tcn_config / lstm_config 采样生成 model_config.config；cate=0 返回空或固定 config。"""
        def sample_int_range(d: Dict[str, Any], key: str) -> Optional[int]:
            r = d.get(key)
            if r is None or not isinstance(r, (list, tuple)) or len(r) < 2:
                return None
            return rng.randint(int(r[0]), int(r[1]))

        if cate == 1:
            tcn = model_cfg.get('tcn_config') or {}
            length = sample_int_range(tcn, 'num_channels_len_range')
            if length is None:
                length = 2
            length = max(1, min(3, length))
            ch_range = tcn.get('num_channels_range')
            if ch_range and isinstance(ch_range, (list, tuple)) and len(ch_range) >= 2:
                num_channels = [rng.randint(int(ch_range[0]), int(ch_range[1])) for _ in range(length)]
            else:
                num_channels = [64] * length
            kernel_options = tcn.get('kernel_size_options')
            kernel_size = int(rng.choice(kernel_options)) if kernel_options else 3
            return {'num_channels': num_channels, 'kernel_size': kernel_size}

        if cate == 2:
            lstm = model_cfg.get('lstm_config') or {}
            hidden_size = sample_int_range(lstm, 'hidden_size_range') or 64
            num_layers = sample_int_range(lstm, 'num_layers_range') or 1
            bidir_opts = lstm.get('bidirectional_options')
            bidirectional = bool(rng.choice(bidir_opts)) if bidir_opts else False
            return {'hidden_size': hidden_size, 'num_layers': num_layers, 'bidirectional': bidirectional}

        return model_cfg.get('config', {})

    def _sample_train_config(self, tc: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
        """根据 hyparam.meta.train_config 的 range 生成单条 train_config（Node 端格式）。仅含随机项：seed, m, mask_len, model_config, reinforcement_config, reward_config。"""
        out: Dict[str, Any] = {}

        def sample_int_range(key: str) -> Optional[int]:
            r = tc.get(key)
            if r is None or not isinstance(r, (list, tuple)) or len(r) < 2:
                return None
            return rng.randint(int(r[0]), int(r[1]))

        seed = sample_int_range('seed_range')
        if seed is not None:
            out['seed'] = seed
        m = sample_int_range('m_range')
        if m is not None:
            out['m'] = m
        mask_len = sample_int_range('mask_len_range')
        if mask_len is not None:
            out['mask_len'] = mask_len

        def sample_float_range(d: Dict[str, Any], key: str) -> Optional[float]:
            r = d.get(key)
            if r is None or not isinstance(r, (list, tuple)) or len(r) < 2:
                return None
            return rng.uniform(float(r[0]), float(r[1]))

        model_cfg = tc.get('model_config') or {}
        cate_type = model_cfg.get('cate_type')
        dropout = sample_float_range(model_cfg, 'dropout_range')
        if dropout is None:
            dropout = 0.0
        if isinstance(cate_type, list) and cate_type:
            cate = rng.choice(cate_type)
            config = self._sample_model_config_by_cate(model_cfg, cate, rng)
            out['model_config'] = {'cate': cate, 'config': config, 'dropout': dropout}
        else:
            out['model_config'] = {'cate': 0, 'config': {}, 'dropout': dropout}

        def sample_float_from(d: Dict[str, Any], key: str) -> Optional[float]:
            r = d.get(key)
            if r is None or not isinstance(r, (list, tuple)) or len(r) < 2:
                return None
            return rng.uniform(float(r[0]), float(r[1]))

        rl_cfg = tc.get('reinforcement_config') or {}
        rl_cate = rl_cfg.get('cate')
        if isinstance(rl_cate, list) and rl_cate:
            opt = {}
            lr = sample_float_from(rl_cfg, 'lr_range') or rng.uniform(1e-5, 1e-3)
            opt['lr'] = lr
            clip = sample_float_from(rl_cfg, 'clip_grad_norm_range')
            if clip is not None:
                opt['clip_grad_norm'] = clip
            wd = sample_float_from(rl_cfg, 'weight_decay_range')
            if wd is not None:
                opt['weight_decay'] = wd
            out['reinforcement_config'] = {'cate': rng.choice(rl_cate), 'opt': opt}
        else:
            out['reinforcement_config'] = {'cate': 0, 'opt': {'lr': 1e-4}}

        # 从配置文件读取reward_config范围设置
        rw_cfg = tc.get('reward_config') or {}
        keys = ['rtr', 'vol', 'sharpe', 'max_drawdown', 'diversification']

        # 为每个权重从配置中读取范围，如果没有配置则使用默认值
        raw = []
        for key in keys:
            range_key = f'{key}_range'
            range_val = rw_cfg.get(range_key)
            if range_val and isinstance(range_val, (list, tuple)) and len(range_val) >= 2:
                # 使用配置的范围
                weight = rng.uniform(float(range_val[0]), float(range_val[1]))
            else:
                # 使用默认范围
                weight = rng.uniform(0.01, 1.0)
            raw.append(weight)

        total = sum(raw)
        out['reward_config'] = {'reward_weights': {k: v / total for k, v in zip(keys, raw)}}

        # 经典效用函数风险系数 A：对数正态分布 A = exp(N(mu, sigma))，配置为 [mu, sigma]
        a_cfg = rw_cfg.get('A')
        if a_cfg is not None and isinstance(a_cfg, (list, tuple)) and len(a_cfg) >= 2:
            mu, sigma = float(a_cfg[0]), float(a_cfg[1])
            z = rng.gauss(mu, sigma)
            a_val = math.exp(z)
            # 裁剪到合理范围，避免数值问题
            a_val = max(0.01, min(20.0, a_val))
            out['reward_config']['A'] = a_val

        return out

    def generate_shared_meta(self, task_id: str) -> Dict[str, Any]:
        """生成所有节点共享的meta配置（不含train_config）；stock_list 由 get_code_list 取（含分段），与数据加载一致"""
        meta = self._meta_param or {}
        stock_list = get_code_list()
        if len(stock_list) == 0:
            logger.error("get_code_list 返回空列表，发布 shutdown 并中止当前任务")
            MESSAGE_BUS.publish(
                message=ShutdownMessage(
                    message_type="shutdown",
                    publisher=self.__class__.__name__,
                    payload=ShutdownPayload(
                        reason="empty_stock_list",
                        graceful=True,
                        timeout=300,
                    ),
                )
            )
            raise ValueError("get_code_list 返回空，已发布 shutdown，请检查配置与数据后重跑")

        return {
            'task_id': task_id,
            'start_year': int(meta.get('start_year', 1997)),
            'end_year': int(meta.get('end_year', 2025)),
            'N': len(stock_list),
            'stock_list': list(stock_list),
            'earliest_year_month': list(self._parse_earliest_year_month(
                meta.get('earliest_year_month', (1997, 1)))),
            'n': int(meta.get('n', 10)),
            'max_portfolios_num': int(meta.get('max_portfolios_num', 500)),
            'env_config': dict(copy.deepcopy(meta.get('env_config') or {})),
            'performance_config': dict(copy.deepcopy(meta.get('performance_config') or {})),
            'short_limit': float(meta.get('short_limit', 0.0)),
            'checkpoint': bool(meta.get('checkpoint', False)),
            'factors_list': [],  # 由节点本地提供
        }

    @deprecated("use generate_train_configs instead")
    def generate_train_configs(self, num: int) -> List[Dict[str, Any]]:
        """为指定数量的节点生成不同的train_config"""
        meta = self._meta_param or {}
        tc_template = meta.get('train_config') or {}

        rng = random.Random(self._meta_seed)
        train_configs = []

        for i in range(num):
            train_config = self._sample_train_config(tc_template, rng)
            canonical = json.dumps(train_config, sort_keys=True)
            train_config['config_uuid'] = str(uuid.uuid5(uuid.NAMESPACE_DNS, canonical))
            train_configs.append(train_config)

        logger.info(f"生成 {num} 个节点的 train_config")
        return train_configs

    def generate_node_meta(self, num: int, task_id: str) -> List[Dict[str, Any]]:
        """随机化生成节点 meta，所有 meta 共享同一 task_id。约定：顶层 = 固定，train_config = 随机。

        兼容性函数：使用新的generate_shared_meta和generate_train_configs方法组合完整meta。
        """
        if num <= 0:
            return []

        # 获取共享配置
        shared_meta = self.generate_shared_meta(task_id)

        # 获取个性化配置
        train_configs = self.generate_train_configs(num)

        # 组合完整meta
        meta_list = []
        for train_config in train_configs:
            full_meta = {**shared_meta, 'train_config': train_config}
            meta_list.append(full_meta)

        logger.info(f"生成 {num} 条节点 meta，task_id: {task_id}")
        return meta_list

    # ============================ 启动节点 ============================
    def _send_task_to_node(self, host: str, port: int, task_id: str, train_config: Dict[str, Any]) -> Dict[str, Any]:
        """向单个节点发送 req=1 启动任务，TCP 发送 {"req": 1, "task_id": task_id, "train_config": train_config}，返回节点 JSON 响应。"""
        web = self._node_config.get('web', {})
        connect_timeout = float(web.get('timeout', 10))
        payload = json.dumps({"req": 1, "task_id": task_id, "train_config": train_config}).encode('utf-8')
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)
            sock.connect((host, port))
            sock.sendall(payload)
            sock.settimeout(connect_timeout)
            data = sock.recv(8192).decode('utf-8', errors='replace').strip()
            if not data:
                return {"error": "empty response"}
            return json.loads(data)
        except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError, OSError) as e:
            logger.debug(f"端口 {port} 发送任务失败: {e}")
            return {"error": str(e)}
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def _start_single_node(self, host: str, port: int, train_config: Dict[str, Any], task_id: str) -> bool:
        """启动单个节点：发送 req=1 和 train_config，成功则返回 True（响应含 success），否则 False。"""
        resp = self._send_task_to_node(host, port, task_id, train_config)
        if isinstance(resp, dict) and resp.get("success") == "start success":
            logger.info(f"节点 {host}:{port} 启动成功, task_id: {task_id}")
            return True
        err = resp.get("error", resp) if isinstance(resp, dict) else resp
        logger.warning(f"节点 {host}:{port} 启动失败: {err}")
        return False

    def start_nodes(self, train_config_list: List[Dict[str, Any]], task_id: str) -> Tuple[int, int]:
        """按端口在范围内的下标分配 train_config：端口 port 固定使用 train_config_list[port - start_port]，通过 TCP 下发。
        同一端口多次运行获得相同 config；某端口挂了不影响其他端口的分配。
        """
        if not train_config_list:
            return 0, 0
        web = self._node_config.get('web', {})
        host = web.get('node_host', 'localhost')
        start_port, _, _ = self._get_port_range()
        available_str = self.get_all_available_port()
        available = [int(p) for p in available_str]
        ok, fail = 0, 0
        for port in available:
            index = port - start_port
            if 0 <= index < len(train_config_list):
                if self._start_single_node(host, port, train_config_list[index], task_id):
                    ok += 1
                else:
                    fail += 1
        logger.info(f"节点启动完成: 成功 {ok}, 失败 {fail}, 共 {len(available)} 个可用端口（train_config 共 {len(train_config_list)} 份，按端口下标分配）")
        return ok, fail

    # ============================ 停止节点 ============================
    def _send_stop_to_node(self, host: str, port: int) -> Dict[str, Any]:
        """向单个节点发送 req=-1 停止命令，TCP 发送 {"req": -1}，返回节点 JSON 响应。"""
        web = self._node_config.get('web', {})
        connect_timeout = float(web.get('timeout', 10))
        payload = json.dumps({"req": -1}).encode('utf-8')
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)
            sock.connect((host, port))
            sock.sendall(payload)
            sock.settimeout(connect_timeout)
            data = sock.recv(8192).decode('utf-8', errors='replace').strip()
            if not data:
                return {"error": "empty response"}
            return json.loads(data)
        except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError, OSError) as e:
            logger.debug(f"端口 {port} 发送停止命令失败: {e}")
            return {"error": str(e)}
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def stop_single_node(self, port: int) -> bool:
        """停止单个节点
        
        Args:
            port: 节点端口号
        
        Returns:
            bool: 停止成功返回 True，否则返回 False
        """
        web = self._node_config.get('web', {})
        host = web.get('node_host', 'localhost')
        
        resp = self._send_stop_to_node(host, port)
        if isinstance(resp, dict) and resp.get("stop") == "success":
            logger.info(f"节点 {host}:{port} 停止成功")
            return True
        err = resp.get("error", resp) if isinstance(resp, dict) else resp
        logger.warning(f"节点 {host}:{port} 停止失败: {err}")
        return False

    def stop_nodes_by_task_id(self, task_id: str) -> Tuple[int, int]:
        """停止所有运行指定 task_id 的节点
        
        Args:
            task_id: 任务ID
        
        Returns:
            Tuple[int, int]: (成功数, 失败数)
        """
        # 获取运行该 task_id 的所有端口
        running_ports_str = self.get_all_running_task_port(task_id)
        if not running_ports_str:
            logger.info(f"没有运行 task_id={task_id} 的节点")
            return 0, 0
        
        running_ports = [int(port) for port in running_ports_str]
        logger.info(f"准备停止 {len(running_ports)} 个运行 task_id={task_id} 的节点，端口: {running_ports}")
        
        ok, fail = 0, 0
        for port in running_ports:
            if self.stop_single_node(port):
                ok += 1
            else:
                fail += 1
        
        logger.info(f"节点停止完成: 成功 {ok}, 失败 {fail}, 共 {len(running_ports)} 个节点")
        return ok, fail

    def stop_all_nodes(self, wait_after_seconds: float = 2.0) -> Tuple[int, int]:
        """停止当前任务的所有节点（从 Redis 读取 task_id），停止后等待并再检查一次。
        
        Args:
            wait_after_seconds: 发送停止后等待秒数，再检查是否仍有节点在跑。
        
        Returns:
            Tuple[int, int]: (成功数, 失败数)，与 stop_nodes_by_task_id 一致。
        """
        task_id_key = REDIS_PREFIX_MANAGER.build_task_id_key()
        raw = self._redis_client.get(task_id_key)
        current_task_id = (raw.decode('utf-8') if isinstance(raw, bytes) else raw) if raw else None
        if not current_task_id:
            logger.info("无当前 task_id，跳过停止节点")
            return 0, 0
        ok, fail = self.stop_nodes_by_task_id(current_task_id)
        if ok + fail > 0 and wait_after_seconds > 0:
            time.sleep(wait_after_seconds)
            still_running = self.get_all_running_task_port(current_task_id)
            if still_running:
                logger.warning(f"shutdown 后仍有节点未停止 task_id={current_task_id}, 端口: {still_running}")
        return ok, fail

    # =========================== 节点监控线程 =================================
    def _monitor_loop(self):
        """
        节点监控循环
        - 首次检查延后 interval×first_delay_multiplier 秒（默认 3 倍），避免启动时写出 node_num=0 导致数据过期误删
        - 之后每 interval 秒查询所有节点状态，仅统计当前 task_id（Redis 中的 task_id）的节点
        - 保存到 Redis (gt:system:node_info)：node_num、last_update、nodes_record（三字段，无冗余）
        - 若无当前 task_id 或无在跑节点，则 node_num=0，nodes_record=[]，保留字段结构
        """
        monitor_config = self._node_config.get('monitor', {})
        interval = float(monitor_config.get('interval', 120))
        first_delay_multiplier = int(monitor_config.get('first_delay_multiplier', 3))

        logger.info(f"节点监控器启动，监控间隔: {interval} 秒")

        # 首次检查延后，避免启动时节点尚未就绪写出 node_num=0，导致数据过期逻辑按 1 删除
        first_delay = interval * first_delay_multiplier
        logger.info(f"首次节点检查延后 {first_delay:.0f} 秒（interval×{first_delay_multiplier}），避免误删未拉齐数据")
        if not interruptible_sleep(first_delay, lambda: self.monitor_started, check_interval=1.0):
            return

        while self.monitor_started:
            try:
                # 当前 task_id 来自 Redis
                task_id_key = REDIS_PREFIX_MANAGER.build_task_id_key()
                raw = self._redis_client.get(task_id_key)
                current_task_id = (raw.decode('utf-8') if isinstance(raw, bytes) else raw) if raw else None
                if not current_task_id:
                    current_task_id = ""
                
                # 获取所有节点状态
                all_status = self.get_all_status()
                
                # 仅统计当前 task_id 的节点
                current_nodes: List[Dict[str, Any]] = []
                for port, status in all_status.items():
                    if status.get('running') != 1:
                        continue
                    if current_task_id and status.get('task_id') != current_task_id:
                        continue
                    current_nodes.append({
                        'port': port,
                        'node_id': status.get('node_id'),
                        'pid': status.get('pid'),
                        'current_year_month': status.get('current_year_month'),
                    })
                
                # 活跃节点ID列表
                running_node_ids = [node['node_id'] for node in current_nodes if node.get('node_id')]

                # 两字段：running_nodes、last_update、nodes_record
                node_info_key = REDIS_PREFIX_MANAGER.build_node_info_key()
                node_info_data = {
                    'running_nodes': json.dumps(running_node_ids),
                    'last_update': str(int(time.time())),
                    'nodes_record': json.dumps(current_nodes, ensure_ascii=False),
                }
                self._redis_client.hset(node_info_key, mapping=node_info_data)

                # 运行端口列表
                running_ports = [node['port'] for node in current_nodes]
                logger.info(
                    f"节点监控更新: 当前 task_id={current_task_id or '(无)'}, "
                    f"运行端口: {running_ports}"
                )
                
            except Exception as e:
                logger.error(f"节点监控循环异常: {e}", exc_info=True)
            
            # 等待 interval 秒后继续下一次监控（可中断，便于停止时快速退出）
            if self.monitor_started:
                if not interruptible_sleep(interval, lambda: self.monitor_started, check_interval=1.0):
                    break

    def start_monitor(self):
        """启动节点监控器"""
        with self._monitor_lock:
            if self.monitor_started:
                logger.warning('节点监控器已经启动')
                return
            
            self.monitor_started = True
            
            # 创建并启动监控线程
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="NodeMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            logger.info('节点监控器已启动')

    def stop_monitor(self, timeout: float = 10.0) -> bool:
        """停止节点监控器
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        with self._monitor_lock:
            if not self.monitor_started:
                logger.warning('节点监控器未启动')
                return True
            
            self.monitor_started = False
        
        # 等待监控线程结束
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.info(f'等待监控线程结束（超时: {timeout}秒）...')
            self._monitor_thread.join(timeout=timeout)
            
            if self._monitor_thread.is_alive():
                logger.warning(f'监控线程未能在{timeout}秒内停止')
                return False
            else:
                logger.info('监控线程已成功停止')
        
        # 停止等待线程
        with self._waiting_lock:
            self.waiting_for_nodes = False
        
        if self._waiting_thread and self._waiting_thread.is_alive():
            logger.info(f'等待 waiting 线程结束（超时: {timeout}秒）...')
            self._waiting_thread.join(timeout=timeout)
            
            if self._waiting_thread.is_alive():
                logger.warning(f'waiting 线程未能在{timeout}秒内停止')
            else:
                logger.info('waiting 线程已成功停止')
        
        with self._monitor_lock:
            self._monitor_thread = None
        
        with self._waiting_lock:
            self._waiting_thread = None
        
        logger.info('节点监控器已完全停止')
        return True

    # ============================ 等待节点完成 ============================
    def _waiting_loop(self, task_id: str):
        """等待所有运行指定 task_id 的节点完成

        Args:
            task_id: 任务ID
        """
        check_interval = 30  # 检查间隔（秒）
        max_wait_time = 24 * 3600  # 最大等待时间（24小时，任务启动时挂上的等待）
        start_wait_time = time.time()
        consecutive_empty_count = 0  # 连续空闲计数器

        logger.info(f'开始等待 task_id={task_id} 的所有节点完成（需要连续{self._shutdown_confirm_count}次确认）')

        while self.waiting_for_nodes:
            try:
                # 检查是否超时
                elapsed_time = time.time() - start_wait_time
                if elapsed_time > max_wait_time:
                    logger.warning(f'等待节点完成超时（{max_wait_time}秒），task_id={task_id}')
                    break

                # 获取运行该 task_id 的节点
                running_ports = self.get_all_running_task_port(task_id)

                if len(running_ports) == 0:
                    consecutive_empty_count += 1
                    logger.info(f'检测到无运行节点 ({consecutive_empty_count}/{self._shutdown_confirm_count})，task_id={task_id}')

                    if consecutive_empty_count >= self._shutdown_confirm_count:
                        logger.info(f'连续{self._shutdown_confirm_count}次检测到无运行节点，确认任务完成，发布shutdown事件')
                        # 发布 shutdown 事件
                        self._publish_shutdown()
                        break
                else:
                    # 有节点运行，重置计数器
                    if consecutive_empty_count > 0:
                        logger.info(f'检测到节点重新运行，重置确认计数器（{len(running_ports)}个节点在运行）')
                        consecutive_empty_count = 0
                    logger.info(f'仍有 {len(running_ports)} 个节点在运行 task_id={task_id}，端口: {running_ports}')

                # 等待一段时间后继续检查（可中断）
                if not interruptible_sleep(check_interval, lambda: self.waiting_for_nodes, check_interval=1.0):
                    break

            except Exception as e:
                logger.error(f'等待循环异常: {e}', exc_info=True)
                if not interruptible_sleep(check_interval, lambda: self.waiting_for_nodes, check_interval=1.0):
                    break

        logger.info(f'等待线程结束，task_id={task_id}')

    def _publish_shutdown(self):
        """发布 shutdown 事件"""
        payload = ShutdownPayload(
            reason='reached_end_year',
            graceful=True,
            timeout=300  # 5分钟超时
        )
        shutdown_message = ShutdownMessage(
            message_type='shutdown',
            publisher=self.__class__.__name__,
            payload=payload
        )
        
        MESSAGE_BUS.publish(message=shutdown_message)
        logger.info(f'发布 shutdown 事件: reason=reached_end_year, graceful=True')

    def waiting_handler(self, message: Message):
        """处理 waiting 消息，启动等待线程
        
        Args:
            message: WaitingMessage
        """
        payload = message.get('payload', {})
        task_id = payload.get('task_id', 'unknown')
        reason = payload.get('reason', 'unknown')
        end_year = payload.get('end_year', 0)
        current_year = payload.get('current_year', 0)
        
        logger.info(f'收到 waiting 消息: task_id={task_id}, reason={reason}, end_year={end_year}, current_year={current_year}')
        
        with self._waiting_lock:
            # 避免重复启动
            if self.waiting_for_nodes:
                logger.warning('等待线程已启动，跳过重复启动')
                return
            
            self.waiting_for_nodes = True
        
        # 启动等待线程
        self._waiting_thread = threading.Thread(
            target=self._waiting_loop,
            args=(task_id,),
            name="WaitingForNodes",
            daemon=True
        )
        self._waiting_thread.start()
        logger.info(f'等待线程已启动，等待 task_id={task_id} 的所有节点完成')

    # ============================ init / start 消息handler ============================
    def _init_node_info_with_port_count(self) -> None:
        """在启动冗余监控前，将 node_info 的 node_num 初始化为配置的暴露端口数量，避免过期监控误删数据。"""
        start_port, end_port, port_count = self._get_port_range()
        node_info_key = REDIS_PREFIX_MANAGER.build_node_info_key()
        node_info_data = {
            'node_num': str(port_count),
            'last_update': str(int(time.time())),
            'nodes_record': '[]',
        }
        self._redis_client.hset(node_info_key, mapping=node_info_data)
        logger.info(f"已初始化 node_info: node_num={port_count}（暴露端口数 {start_port}～{end_port}）")

    def init_handler(self, message: Message):
        """处理 init：发布 start，等待 30s 后获取可用端口、生成 meta 并启动所有节点。"""
        logger.info("收到 init 消息：发布 start，30s 后启动节点")

        # 从 Redis 获取 task_id
        task_id_key = REDIS_PREFIX_MANAGER.build_task_id_key()
        task_id_raw = self._redis_client.get(task_id_key)
        if task_id_raw is None:
            logger.error("Redis 中无 task_id，跳过启动节点")
            return
        task_id = task_id_raw.decode('utf-8') if isinstance(task_id_raw, bytes) else str(task_id_raw)
        
        # 先初始化 node_info（node_num=暴露端口数），再发 start，避免冗余/过期监控误删数据
        self._init_node_info_with_port_count()

        # 初始化元数据
        meta_key = REDIS_PREFIX_MANAGER.build_meta_key()
        meta = self.generate_shared_meta(task_id)
        meta_json = json.dumps(meta, ensure_ascii=False)
        self._redis_client.set(meta_key, meta_json)
        logger.info(f"已初始化 meta: task_id={task_id}")

        # 发布 start（DataRedundancyMonitor 等据此启动）
        start_msg = StartMessage(
            message_type='start',
            publisher=self.__class__.__name__,
            payload=StartMessagePayload()
        )
        MESSAGE_BUS.publish(message=start_msg)
        
        # 等待 30s
        time.sleep(30)
        logger.debug("等待 30s , 确保数据完成加载")
        
        # 固定按端口范围数量生成 train_config，按端口下标分配（同一端口始终获得同一 config）
        _, _, port_count = self._get_port_range()
        train_config_list = self.generate_train_configs(num=port_count)
        available = self.get_all_available_port()
        if len(available) == 0:
            logger.warning("无可用端口，跳过启动节点")
            return
        ok, fail = self.start_nodes(train_config_list, task_id)
        logger.info(f"init_handler 完成：已启动节点 成功={ok}, 失败={fail}")
        
        # 节点已启动后发布 waiting，启动等待线程（等所有节点完成后发 shutdown），超时 24h
        wait_payload = WaitingPayload(
            task_id=task_id,
            reason='task_started',
            end_year=0,
            current_year=0,
        )
        MESSAGE_BUS.publish(message=WaitingMessage(
            message_type='waiting',
            publisher=self.__class__.__name__,
            payload=wait_payload,
        ))
        logger.info(f"已发布 waiting 消息，task_id={task_id}，等待节点完成后将发布 shutdown")

    def start_handler(self, message: Message):
        """收到 start 后启动节点监控器。"""
        logger.info("收到 start 消息，启动节点监控器")
        self.start_monitor()

    def clearport_handler(self, message: Message):
        """清空端口池：监听到 clearport 后调用 clear_ports。"""
        logger.info("收到 clearport 消息，执行清空端口池")
        ok = self.clear_ports()
        logger.info(f"clear_ports 结果: {ok}")

    def shutdown_handler(self, message: Message):
        """收到 shutdown 后先停止当前任务的所有节点，再停止节点监控器与等待线程。"""
        logger.info("收到 shutdown 消息，停止当前任务节点并停止节点监控器")
        self.stop_all_nodes(wait_after_seconds=2.0)
        self.stop_monitor(timeout=10.0)

    def _subscribe(self):
        """订阅消息处理器"""
        MESSAGE_BUS.subscribe('init', self.init_handler, 'NodeManager')
        MESSAGE_BUS.subscribe('start', self.start_handler, 'NodeManager')
        MESSAGE_BUS.subscribe('waiting', self.waiting_handler, 'NodeManager')
        MESSAGE_BUS.subscribe('clearport', self.clearport_handler, 'NodeManager')
        MESSAGE_BUS.subscribe('shutdown', self.shutdown_handler, 'NodeManager')

NODE_MANAGER = NodeManager()