#!/bin/bash
# frp客户端停止脚本

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

echo "=== 停止frp客户端 ==="

# 检查是否在运行
if ! pgrep -f "frpc -c frp/frpc.ini" > /dev/null; then
    log_warn "frp客户端未运行"
    exit 0
fi

# 获取PID用于显示
FRP_PID=$(pgrep -f "frpc -c frp/frpc.ini")
log_info "正在停止frp客户端 (PID: $FRP_PID)..."

# 停止frp进程
pkill -f "frpc"

# 等待停止完成
sleep 2

# 检查停止结果
if pgrep -f "frpc" > /dev/null; then
    log_error "frp客户端停止失败，尝试强制停止..."
    pkill -9 -f "frpc"
    sleep 1

    if pgrep -f "frpc" > /dev/null; then
        log_error "强制停止也失败，请手动检查进程"
        exit 1
    else
        log_warn "frp客户端已被强制停止"
    fi
else
    log_info "frp客户端已停止"
fi
