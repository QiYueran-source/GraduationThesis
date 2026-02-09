"""
向所有端口发送 req=2，打印各端口响应信息。
端口与主机从 src/config/node.yaml 的 web.node_host、web.port_range 读取，未配置则用默认值。
"""
import json
import socket
import yaml
from pathlib import Path

# 配置：端口范围与主机
def _load_config():
    config_path = Path(__file__).resolve().parent / 'src' / 'config' / 'node.yaml'
    if not config_path.exists():
        return 'localhost', 8191, 8220, 2.0
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            node_config = yaml.safe_load(f) or {}
    except Exception:
        return 'localhost', 8191, 8220, 2.0
    web = node_config.get('web', {})
    host = web.get('node_host', 'localhost')
    pr = web.get('port_range', [8191, 8220])
    start_port = int(pr[0])
    end_port = int(pr[1])
    timeout = float(web.get('timeout', 2.0))
    return host, start_port, end_port, timeout


def _send_req2(host: str, port: int, timeout: float) -> dict | None:
    """向指定端口发送 {"req": 2}，返回解析后的响应或 None。"""
    payload = json.dumps({"req": 2}).encode('utf-8')
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(payload)
        sock.settimeout(timeout)
        data = sock.recv(4096).decode('utf-8', errors='replace').strip()
        if not data:
            return None
        return json.loads(data)
    except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError, OSError) as e:
        return {"_error": str(e)}
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def main():
    host, start_port, end_port, timeout = _load_config()
    print(f"host={host}, port_range=[{start_port}, {end_port}], timeout={timeout}s")
    print("发送 req=2 到各端口，打印响应：\n")
    for port in range(start_port, end_port + 1):
        resp = _send_req2(host, port, timeout)
        if resp is None:
            print(f"  {port}: (无响应或空)")
        else:
            print(f"  {port}: {resp}")


if __name__ == "__main__":
    main()
