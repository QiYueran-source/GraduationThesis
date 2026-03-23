#!/bin/bash

# 定义映射关系
declare -A node_map=(
    ["node_1772014470_25173"]="a1_1"
    ["node_1772014488_6824"]="a1_2"
    ["node_1772014501_6831"]="a1_3"
    ["node_1772014583_23544"]="a1_4"
    ["node_1772014595_27084"]="a1_5"
    ["node_1772031879_25181"]="a1_6"
    ["node_1772031891_9646"]="a1_7"
    ["node_1772031901_11800"]="a1_8"
    ["node_1772031921_19551"]="a1_9"
    ["node_1772033480_1918"]="a1_10"
)

# 找到所有相关的任务目录
task_dirs=$(find result -type d -name "2026022[5-8]_*" | sort)

for task_dir in $task_dirs; do
    echo "Processing $task_dir"
    
    # 找到该任务目录下的所有node目录
    node_dirs=$(find "$task_dir" -name "node_*" -type d)
    
    for node_dir in $node_dirs; do
        node_name=$(basename "$node_dir")
        
        # 如果该node名称在映射表中，则重命名
        if [[ ${node_map[$node_name]} ]]; then
            new_name=${node_map[$node_name]}
            new_path="$task_dir/$new_name"
            echo "  Renaming $node_name -> $new_name"
            mv "$node_dir" "$new_path"
        else
            echo "  Skipping $node_name (not in mapping)"
        fi
    done
done

echo "Renaming completed!"
