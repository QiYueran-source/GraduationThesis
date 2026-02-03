"""
节点管理器    
1.访问所有端口，获取可用端口  
2.初始化参数，发送给各个端口  
3.隔一段时间请求一次状态，查看还有多少端口在运行 
4.如果所有端口运行完毕，发布结束消息  
"""
# 库
import yaml
import time
import json
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__,'[NodeManager]')

class NodeManager:
    def __init__(self):
        # 配置 
        self._config = {}

        # 线程管理
        self.monitor_started = False

        # 加载配置
        self._load_config()

    def _load_config(self):
        """加载配置"""
        try:
            with open('src/config/node.yaml', 'r', encoding = 'utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise 

    def clear_ports(self) -> bool:
        """清空端口池：调用微服务 DELETE /clear，将所有已分配端口移回可用队列。"""
        host = self._config.get('web',{}).get('ms_clear_host', '43.139.192.176')
        port = self._config.get('web',{}).get('ms_clear_port', 8190)
        base = f"http://{host}:{port}"
        url = self._config.get('web',{}).get('ms_clear_url', '/clear')

        try:
            response = requests.delete(base + url, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"清空端口请求失败: {e}")
            return False

    def _check_single_port(
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
        web = self._config.get('web', {})
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
                executor.submit(self._check_single_port, host, port, payload, connect_timeout): port
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


    