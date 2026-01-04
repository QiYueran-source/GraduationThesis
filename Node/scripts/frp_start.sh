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
if [ ! -f "frp/frpc.toml" ]; then
    log_error "frp/frpc.toml 配置文件不存在"
    log_error "请先配置frp连接信息"
    exit 1
fi

# 检查是否已经在运行（只检查我们配置的frp进程）
# 使用 ps 替代 pgrep（兼容没有 procps 的环境）
FRP_PID=$(ps aux 2>/dev/null | grep -v grep | grep "frpc -c frp/frpc.toml" | awk '{print $2}' | head -1)
if [ -n "$FRP_PID" ]; then
    log_warn "frp客户端已在运行 (PID: $FRP_PID)"
    log_info "如果需要重启，请先运行: ./scripts/frp_stop.sh"
    exit 0
fi

# 创建日志目录
mkdir -p logs

# 启动frp客户端（日志由frpc.toml配置处理）
log_info "启动frp客户端..."
./frp/frpc -c frp/frpc.toml &
FRP_PID=$!

# 等待启动并让frp有机会创建日志文件
sleep 3

# 检查启动结果（使用 ps 替代 pgrep）
# 首先检查进程是否在运行
if ps aux 2>/dev/null | grep -v grep | grep "frpc" > /dev/null; then
    # 获取实际运行的 PID
    ACTUAL_PID=$(ps aux 2>/dev/null | grep -v grep | grep "frpc -c frp/frpc.toml" | awk '{print $2}' | head -1)
    if [ -n "$ACTUAL_PID" ]; then
        log_info "frp客户端启动成功 (PID: $ACTUAL_PID)"
    else
        log_info "frp客户端启动成功 (PID: $FRP_PID)"
    fi
    log_info "日志文件: logs/frpc.log"
    log_info "停止命令: ./scripts/frp_stop.sh"
else
    # 如果进程不在运行，检查日志中是否有成功启动的记录
    if [ -f "logs/frpc.log" ] && grep -q "start proxy success" logs/frpc.log 2>/dev/null; then
        # 检查最近的日志（最近5秒内）
        if tail -20 logs/frpc.log 2>/dev/null | grep -q "start proxy success"; then
            log_warn "frp客户端进程已退出，但代理启动成功"
            log_info "这可能是因为代理配置问题或网络问题"
            log_info "日志文件: logs/frpc.log"
            log_info "请检查日志以获取更多信息"
            exit 0
        fi
    fi
    
    log_error "frp客户端启动失败"
    log_error "请检查配置文件和网络连接"
    log_error "查看日志: cat logs/frpc.log"
    exit 1
fi
