#!/bin/bash

# task_info.sh - 显示指定 task_id 下所有 node 的信息
# 用法: ./task_info.sh <task_id>

if [ $# -ne 1 ]; then
    echo "用法: $0 <task_id>"
    echo "例如: $0 20260226_1214_baseline1_1bfabc20-8ed2-4394-99b2-556b01929c48"
    exit 1
fi

TASK_ID="$1"
RESULT_DIR="./result/$TASK_ID"

if [ ! -d "$RESULT_DIR" ]; then
    echo "错误: 任务目录不存在: $RESULT_DIR"
    exit 1
fi

echo "任务ID: $TASK_ID"
echo "================================================================"
echo "Node ID                              Port    Seed    Config UUID"
echo "================================================================"

# 遍历所有 node 目录
for node_dir in "$RESULT_DIR"/node_*; do
    if [ -d "$node_dir" ]; then
        node_id=$(basename "$node_dir")
        meta_file="$node_dir/meta.json"

        if [ -f "$meta_file" ]; then
            # 使用 Python 解析 JSON 并提取所需字段
            /home/frank/miniconda3/envs/thesis_env/bin/python -c "
import json
import sys

try:
    with open('$meta_file', 'r', encoding='utf-8') as f:
        data = json.load(f)

    port = data.get('port', 'N/A')
    seed = data.get('train_config', {}).get('seed', 'N/A')
    config_uuid = data.get('train_config', {}).get('config_uuid', 'N/A')

    # 格式化输出：node_id 补齐到35字符，port到8字符，seed到8字符
    print(f'{sys.argv[1]:<35} {str(port):<8} {str(seed):<8} {config_uuid}')

except Exception as e:
    print(f'{sys.argv[1]:<35} ERROR: {str(e)[:50]}')
" "$node_id"
        else
            echo "$node_id                           N/A     N/A     meta.json not found"
        fi
    fi
done

echo "================================================================"