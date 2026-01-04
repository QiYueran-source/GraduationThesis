#!/usr/bin/env python3
import os
import socket

port = 4321

# 尝试创建 socket 来测试端口
test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    test_socket.bind(('127.0.0.1', port))
    test_socket.close()
    print(f"端口 {port} 可用")
except OSError:
    print(f"端口 {port} 被占用，尝试查找进程...")
    # 遍历 /proc 查找 Python 进程
    for pid_dir in os.listdir('/proc'):
        if pid_dir.isdigit():
            try:
                cmdline_file = f'/proc/{pid_dir}/cmdline'
                if os.path.exists(cmdline_file):
                    with open(cmdline_file, 'r') as f:
                        cmdline = f.read()
                        if 'test_tcp_server' in cmdline:
                            print(f"找到进程: PID {pid_dir}")
                            os.kill(int(pid_dir), 9)
                            print(f"已停止进程 {pid_dir}")
            except:
                pass