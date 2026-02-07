#!/bin/bash

# 启动rsync 
sudo rsync --daemon --config=/etc/rsyncd.conf

# 工作
/home/frank/miniconda3/envs/thesis_env/bin/python start.py  