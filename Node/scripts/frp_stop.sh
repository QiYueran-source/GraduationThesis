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

# 检查是否在运行（使用 ps 替代 pgrep）
FRP_PID=$(ps aux 2>/dev/null | grep -v grep | grep "frpc -c frp/frpc.toml" | awk '{print $2}' | head -1)
if [ -z "$FRP_PID" ]; then
    log_warn "frp客户端未运行"
    exit 0
fi

# 获取所有 frpc 进程的 PID
ALL_FRP_PIDS=$(ps aux 2>/dev/null | grep -v grep | grep "frpc" | awk '{print $2}')
if [ -z "$ALL_FRP_PIDS" ]; then
    log_warn "frp客户端未运行"
    exit 0
fi

log_info "正在停止frp客户端 (PIDs: $ALL_FRP_PIDS)..."

# 停止所有 frpc 进程
for pid in $ALL_FRP_PIDS; do
    kill $pid 2>/dev/null
done

# 等待停止完成
sleep 2

# 检查停止结果（使用 ps 替代 pgrep）
REMAINING_PIDS=$(ps aux 2>/dev/null | grep -v grep | grep "frpc" | awk '{print $2}')
if [ -n "$REMAINING_PIDS" ]; then
    log_error "frp客户端停止失败，尝试强制停止..."
    for pid in $REMAINING_PIDS; do
        kill -9 $pid 2>/dev/null
    done
    sleep 1

    # 再次检查
    REMAINING_PIDS=$(ps aux 2>/dev/null | grep -v grep | grep "frpc" | awk '{print $2}')
    if [ -n "$REMAINING_PIDS" ]; then
        log_error "强制停止也失败，请手动检查进程"
        exit 1
    else
        log_warn "frp客户端已被强制停止"
    fi
else
    log_info "frp客户端已停止"
fi
