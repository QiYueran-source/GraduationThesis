#!/bin/bash

# 启动 rsync（仅当尚未运行时）
if [ -f /var/run/rsyncd.pid ] && kill -0 "$(cat /var/run/rsyncd.pid)" 2>/dev/null; then
    echo "rsync daemon already running, skip"
else
    sudo rsync --daemon --config=/etc/rsyncd.conf
fi

# 工作
/home/frank/miniconda3/envs/thesis_env/bin/python start.py  