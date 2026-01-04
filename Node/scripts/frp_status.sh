#!/bin/bash
# frp客户端状态检查脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo "=== frp客户端状态检查 ==="

# 检查frp进程（使用 ps 替代 pgrep，兼容没有 procps 的环境）
FRP_PID=$(ps aux 2>/dev/null | grep -v grep | grep "frpc -c frp/frpc.toml" | awk '{print $2}' | head -1)
if [ -n "$FRP_PID" ]; then
    log_info "frp客户端运行中 (PID: $FRP_PID)"
else
    log_error "frp客户端未运行"
fi

# 检查配置文件
if [ -f "frp/frpc.toml" ]; then
    echo -e "${BLUE}[配置]${NC} frpc.toml 存在"
else
    log_error "frpc.toml 配置文件不存在"
fi

# 检查日志文件
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/frpc.log"

if [ -f "$LOG_FILE" ]; then
    echo -e "${BLUE}[日志]${NC} frpc.log 存在"
    echo -e "${BLUE}[日志]${NC} 最后几行:"
    tail -5 "$LOG_FILE" | sed 's/^/    /'
else
    log_warn "frpc.log 日志文件不存在"
    log_info "日志文件应位于: $LOG_FILE"
fi

# 检查frp可执行文件
if [ -f "frp/frpc" ]; then
    FRP_VERSION=$(./frp/frpc --version 2>/dev/null | head -1)
    if [ $? -eq 0 ]; then
        echo -e "${BLUE}[版本]${NC} $FRP_VERSION"
    else
        echo -e "${BLUE}[文件]${NC} frpc 可执行文件存在"
    fi
else
    log_error "frpc 可执行文件不存在"
fi

# 显示使用帮助
echo ""
echo -e "${BLUE}[帮助]${NC} 管理命令:"
echo "  启动: ./scripts/frp_start.sh"
echo "  停止: ./scripts/frp_stop.sh"
echo "  状态: ./scripts/frp_status.sh"
