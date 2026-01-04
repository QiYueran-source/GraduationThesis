#!/bin/bash

# 启动脚本 - 简化版
echo "=== 启动frp客户端 ==="
/Node/frp/frpc -c /Node/frp/frpc.toml &

echo "=== 启动worker进程 ==="
python /Node/worker.py &

echo "=== 启动测试TCP服务器 ==="
python /Node/test_tcp_server.py &

echo "=== 所有服务已启动 ==="

# 打印frp状态
echo "=== 查看frp状态(开发环境) ==="
/Node/scripts/frp_status.sh

# 等待所有后台进程
wait