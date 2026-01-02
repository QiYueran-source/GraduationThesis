#!/bin/bash
# frp客户端启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo "=== 启动frp客户端 ==="

# 检查frp可执行文件
if [ ! -f "frp/frpc" ]; then
    log_error "frp/frpc 文件不存在"
    log_error "请先运行: tar -xzf frp_0.65.0_linux_amd64.tar.gz -C frp --strip-components=1"
    exit 1
fi

# 检查配置文件
if [ ! -f "frp/frpc.ini" ]; then
    log_error "frp/frpc.ini 配置文件不存在"
    log_error "请先配置frp连接信息"
    exit 1
fi

# 检查是否已经在运行（只检查我们配置的frp进程）
if pgrep -f "frpc -c frp/frpc.ini" > /dev/null; then
    FRP_PID=$(pgrep -f "frpc -c frp/frpc.ini")
    log_warn "frp客户端已在运行 (PID: $FRP_PID)"
    log_info "如果需要重启，请先运行: ./scripts/frp_stop.sh"
    exit 0
fi

# 创建日志目录
mkdir -p logs

# 启动frp客户端（日志由frpc.ini配置处理）
log_info "启动frp客户端..."
./frp/frpc -c frp/frpc.ini &
FRP_PID=$!

# 等待启动并让frp有机会创建日志文件
sleep 3

# 检查启动结果
if pgrep -f "frpc" > /dev/null; then
    log_info "frp客户端启动成功 (PID: $FRP_PID)"
    log_info "日志文件: logs/frpc.log"
    log_info "停止命令: ./scripts/frp_stop.sh"
else
    log_error "frp客户端启动失败"
    log_error "请检查配置文件和网络连接"
    log_error "查看日志: cat logs/frpc.log"
    exit 1
fi
