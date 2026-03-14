#!/usr/bin/env bash

# 监控 Redis 中的 gt:system:node_info，不存在则启动 start.py

REDIS_CLI="redis-cli -a Season2004!!?"
REDIS_KEY="gt:system:node_info"

PYTHON_BIN="/home/frank/miniconda3/envs/thesis_env/bin/python"
START_PY="/home/frank/files/programs/GraduationThesis/start.py"

# 轮询间隔（秒）
SLEEP_SECONDS=300

while true; do
  # 检查键是否存在（1=存在，0=不存在）
  value="$($REDIS_CLI EXISTS "$REDIS_KEY" 2>/dev/null)"

  # 如果 Redis 无法连接，给出提示并稍后重试
  if [ $? -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 无法连接 Redis，稍后重试..."
    sleep "$SLEEP_SECONDS"
    continue
  fi

  # 当键不存在时启动脚本
  if [ "$value" = "0" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 检测到 $REDIS_KEY 不存在，启动 start.py"

    # 如果已有正在运行的 start.py，则避免重复启动
    if pgrep -f "$START_PY" >/dev/null 2>&1; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - 检测到已有 start.py 进程在运行，跳过本次启动"
    else
      # 通过管道向 start.py 传入 3 个输入：n, mech1, y（每次输入前等 1 秒，阻塞直至进程结束）
      {
        sleep 1; echo "n"
        sleep 1; echo "mech1"
        sleep 1; echo "y"
      } | "$PYTHON_BIN" "$START_PY"

      echo "$(date '+%Y-%m-%d %H:%M:%S') - start.py 已结束，继续下一轮监控"
    fi
  fi

  sleep "$SLEEP_SECONDS"
done

