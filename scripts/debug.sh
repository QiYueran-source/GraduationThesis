#!/bin/bash

# 向所有端口发送 req=2，打印各端口响应信息。
# 端口与主机从 src/config/node.yaml 的 web.node_host、web.port_range 读取，未配置则用默认值。

/home/frank/miniconda3/envs/thesis_env/bin/python3 -c "
import socket
import json
import yaml
import sys
import os
from pathlib import Path

def load_node_config():
    \"\"\"加载node配置\"\"\"
    # 从脚本目录向上查找配置文件
    script_dir = Path(__file__).parent if '__file__' in globals() else Path.cwd()
    config_path = script_dir.parent / 'src' / 'config' / 'node.yaml'

    # 如果找不到，尝试当前目录
    if not config_path.exists():
        config_path = Path('src/config/node.yaml')

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f'加载配置文件失败: {e}')
        return None

def send_debug_request(host, port, timeout=5):
    \"\"\"向指定端口发送调试请求(req=2)\"\"\"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        # 发送req=2请求
        payload = json.dumps({'req': 2}).encode('utf-8')
        sock.sendall(payload)

        # 接收响应
        response_data = sock.recv(8192).decode('utf-8', errors='replace').strip()

        if response_data:
            response = json.loads(response_data)
            return response
        else:
            return {'error': 'empty response'}

    except socket.timeout:
        return {'error': 'connection timeout'}
    except socket.error as e:
        return {'error': f'socket error: {e}'}
    except json.JSONDecodeError as e:
        return {'error': f'json decode error: {e}'}
    except Exception as e:
        return {'error': f'unexpected error: {e}'}
    finally:
        try:
            sock.close()
        except:
            pass

def main():
    # 加载配置
    config = load_node_config()
    if not config:
        sys.exit(1)

    # 获取主机和端口范围
    web_config = config.get('web', {})
    node_host = web_config.get('node_host', '127.0.0.1')  # 默认localhost
    port_range = web_config.get('port_range', [8191, 8220])  # 默认端口范围

    if isinstance(port_range, list) and len(port_range) == 2:
        start_port, end_port = port_range[0], port_range[1]
    else:
        print('端口范围配置错误，使用默认值 8191-8220')
        start_port, end_port = 8191, 8220

    print(f'开始调试检查，主机: {node_host}, 端口范围: {start_port}-{end_port}')
    print('=' * 60)

    # 遍历所有端口
    active_count = 0
    for port in range(start_port, end_port + 1):
        print(f'检查端口 {port}:')
        response = send_debug_request(node_host, port)

        if 'error' in response:
            print(f'  ❌ 错误: {response[\"error\"]}')
        else:
            debug_info = response.get('debug', False)
            worker_pid = response.get('_worker_pid')
            worker_alive = response.get('worker_alive', False)
            meta = response.get('_meta', {})

            if debug_info:
                status = '✅' if worker_alive else '❌'
                print(f'  {status} 工作进程PID: {worker_pid}')
                print(f'      运行状态: {\"运行中\" if worker_alive else \"未运行\"}')
                if meta:
                    task_id = meta.get('task_id', 'N/A')
                    print(f'      任务ID: {task_id}')
                else:
                    print('      任务信息: 无')

                if worker_alive:
                    active_count += 1
            else:
                print('  ❌ 非调试响应')

        print()

    print('=' * 60)
    print(f'检查完成，共检查 {end_port - start_port + 1} 个端口，发现 {active_count} 个活跃节点')

if __name__ == '__main__':
    main()
"