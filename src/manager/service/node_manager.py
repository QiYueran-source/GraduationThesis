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
import yaml
import time
import json
import socket
import requests
import random
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any, Tuple

# 组件
from src.manager.service.message import (
    Message,
    InitMessage,StartMessage,
    InitMessagePayload,StartMessagePayload
)
from src.manager.database import get_code_list

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__,'[NodeManager]')

class NodeManager:
    def __init__(self):
        # 配置 
        self._node_config = {}
        self._stock_pool_param = {}
        self._meta_param = {}
        self._meta_seed = None  

        # 线程管理
        self.monitor_started = False

        # 加载配置
        self._load_config()

    def _load_config(self):
        """加载配置：node.yaml 为节点/端口配置，hyparam.yaml 为股票池与 meta 配置。"""
        try:
            with open('src/config/node.yaml', 'r', encoding='utf-8') as f:
                self._node_config = yaml.safe_load(f) or {}
            with open('src/config/hyparam.yaml', 'r', encoding='utf-8') as f:
                hyparam = yaml.safe_load(f) or {}
            self._stock_pool_param = hyparam.get('stock_pool', {})
            self._meta_param = hyparam.get('meta', {})
            self._meta_seed = hyparam.get('meta_seed', None)
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

    # ============================ 获取可用端口 ============================
    def _get_single_available_port(
        self,
        host: str,
        port: int,
        payload: bytes,
        connect_timeout: float,
    ) -> Optional[int]:
        """单端口探测：TCP 连接并发送 {"req":0}，能收到合法 JSON 则返回 port，否则返回 None。无容器占用时连接失败，正常返回 None。"""
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)
            sock.connect((host, port))
            sock.sendall(payload)
            sock.settimeout(connect_timeout)
            data = sock.recv(4096).decode('utf-8', errors='replace').strip()
            if not data:
                return None
            obj = json.loads(data)
            return port if isinstance(obj, dict) else None
        except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError, OSError) as e:
            logger.debug(f"端口 {port} 不可用（无容器或超时）: {e}")
            return None
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def get_available_ports(self) -> List[int]:
        """对 port_range 内每个端口并发 TCP 探测（ThreadPoolExecutor），发送 {"req":0}，能收到合法 JSON 的端口视为可用并返回。无容器占用的端口会连接失败，自动跳过。"""
        web = self._node_config.get('web', {})
        host = web.get('node_host', 'localhost')
        pr = web.get('port_range', [8191, 8220])
        start_port = int(pr[0])
        end_port = int(pr[1])
        connect_timeout = float(web.get('timeout', 2.0))
        max_workers = min(end_port - start_port + 1, web.get('max_worker', 32))
        payload = json.dumps({"req": 0}).encode('utf-8')
        total = end_port - start_port + 1

        available: List[int] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._get_single_available_port, host, port, payload, connect_timeout): port
                for port in range(start_port, end_port + 1)
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        available.append(result)
                except Exception as e:
                    port = futures.get(future)
                    logger.debug(f"端口 {port} 探测异常: {e}")

        available.sort()
        logger.info(f"可用端口数: {len(available)}/{total}, 端口: {available}")
        return available

    # ============================ 获取正在运行的端口 ============================
    def _get_single_running_port(
        self,
        host: str,
        port: int,
        payload: bytes,
        connect_timeout: float,
    ) -> Optional[int]:
        """单端口探测：TCP 发 {"req":0}，若响应为合法 JSON 且 running==1 则返回 port，否则返回 None。"""
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout)
            sock.connect((host, port))
            sock.sendall(payload)
            sock.settimeout(connect_timeout)
            data = sock.recv(4096).decode('utf-8', errors='replace').strip()
            if not data:
                return None
            obj = json.loads(data)
            if isinstance(obj, dict) and obj.get("running") == 1:
                return port
            return None
        except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError, OSError) as e:
            logger.debug(f"端口 {port} 未在运行或不可达: {e}")
            return None
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
    
    def get_running_ports(self) -> List[int]:
        """对 port_range 内每个端口并发发 req=0，响应中 running==1 的端口视为正在运行并返回。"""
        web = self._node_config.get('web', {})
        host = web.get('node_host', 'localhost')
        pr = web.get('port_range', [8191, 8220])
        start_port = int(pr[0])
        end_port = int(pr[1])
        connect_timeout = float(web.get('timeout', 2.0))
        max_workers = min(end_port - start_port + 1, web.get('max_worker', 32))
        payload = json.dumps({"req": 0}).encode('utf-8')

        running: List[int] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._get_single_running_port, host, port, payload, connect_timeout): port
                for port in range(start_port, end_port + 1)
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        running.append(result)
                except Exception as e:
                    port = futures.get(future)
                    logger.debug(f"端口 {port} 探测异常: {e}")

        running.sort()
        logger.info(f"正在运行的端口数: {len(running)}, 端口: {running}")
        return running

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
            out['model_config'] = {'cate': rng.choice(cate_type), 'config': model_cfg.get('config', {}), 'dropout': dropout}
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

        keys = ['rtr', 'vol', 'sharpe', 'max_drawdown']
        raw = [rng.uniform(0.01, 1.0) for _ in keys]
        total = sum(raw)
        out['reward_config'] = {'reward_weights': {k: v / total for k, v in zip(keys, raw)}}
        return out

    def generate_node_meta(self, num: int, task_id: str) -> List[Dict[str, Any]]:
        """随机化生成节点 meta，所有 meta 共享同一 task_id。约定：顶层 = 固定，train_config = 随机。"""
        if num <= 0:
            return []

        meta = self._meta_param or {}
        pool_type = self._stock_pool_param.get('pool_type', 'test')
        stock_list = get_code_list(code_type=pool_type)
        N = len(stock_list)
        start_year = int(meta.get('start_year', 1997))
        end_year = int(meta.get('end_year', 2025))
        earliest_year_month = self._parse_earliest_year_month(meta.get('earliest_year_month', (1997, 1)))
        n = int(meta.get('n', 10))
        max_portfolios_num = int(meta.get('max_portfolios_num', 500))
        env_config = dict(copy.deepcopy(meta.get('env_config') or {}))
        performance_config = dict(copy.deepcopy(meta.get('performance_config') or {}))
        tc_template = meta.get('train_config') or {}

        rng = random.Random(self._meta_seed)
        meta_list: List[Dict[str, Any]] = []
        for i in range(num):
            train_config = self._sample_train_config(tc_template, rng)
            meta_list.append({
                'task_id': task_id,
                'start_year': start_year,
                'end_year': end_year,
                'N': N,
                'stock_list': list(stock_list),
                'earliest_year_month': list(earliest_year_month),
                'n': n,
                'max_portfolios_num': max_portfolios_num,
                'env_config': env_config,
                'performance_config': performance_config,
                'factors_list': [],  # 不读取，由节点本地提供
                'train_config': train_config,
            })
        logger.info(f"生成 {num} 条节点 meta，task_id: {task_id}")
        return meta_list

    # ============================ 启动节点 ============================
    def _send_task_to_node(self, host: str, port: int, meta: Dict[str, Any]) -> Dict[str, Any]:
        """向单个节点发送 req=1 启动任务，TCP 发送 {"req": 1, "meta": meta}，返回节点 JSON 响应。"""
        web = self._node_config.get('web', {})
        connect_timeout = float(web.get('timeout', 10))
        payload = json.dumps({"req": 1, "meta": meta}).encode('utf-8')
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

    def _start_single_node(self, host: str, port: int, meta: Dict[str, Any]) -> bool:
        """启动单个节点：发送 req=1，成功则返回 True（响应含 success），否则 False。"""
        resp = self._send_task_to_node(host, port, meta)
        if isinstance(resp, dict) and resp.get("success") == "start success":
            logger.info(f"节点 {host}:{port} 启动成功, task_id: {meta.get('task_id', '')}")
            return True
        err = resp.get("error", resp) if isinstance(resp, dict) else resp
        logger.warning(f"节点 {host}:{port} 启动失败: {err}")
        return False

    def start_nodes(self, meta_list: List[Dict[str, Any]]) -> Tuple[int, int]:
        """按可用端口顺序向各节点下发 meta 启动任务。
        - 先 get_available_ports()，取前 len(meta_list) 个端口与 meta_list 一一对应下发。
        - 返回 (成功数, 失败数)。
        """
        if not meta_list:
            return 0, 0
        web = self._node_config.get('web', {})
        host = web.get('node_host', 'localhost')
        available = self.get_available_ports()
        if len(available) < len(meta_list):
            logger.warning(f"可用端口数 {len(available)} 小于 meta 数 {len(meta_list)}，仅启动前 {len(available)} 个节点")
        ports = available[: len(meta_list)]
        ok, fail = 0, 0
        for port, meta in zip(ports, meta_list):
            if self._start_single_node(host, port, meta):
                ok += 1
            else:
                fail += 1
        logger.info(f"节点启动完成: 成功 {ok}, 失败 {fail}, 共 {len(meta_list)} 条 meta")
        return ok, fail

    # ============================ 初始化消息handler ============================
    def init_handler(self, message:Message):
        """初始化消息handler
        1.清理端口  
        2.input = y 后，发布start事件  
        """
        logger.info(f"开始初始化")

        
    