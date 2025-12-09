#!/bin/bash

# 定义源目录和目标目录
SOURCE_DIR="/mnt/e/齐悦然的文件/forwsl"
TARGET_DIR="/home/frank/files/programs/GraduationThesis/tmp"

# 检查源目录是否存在
if [ ! -d "$SOURCE_DIR" ]; then
    echo "错误：源目录 $SOURCE_DIR 不存在！"
    exit 1
fi

# 检查目标目录是否存在，如果不存在则创建
if [ ! -d "$TARGET_DIR" ]; then
    echo "目标目录 $TARGET_DIR 不存在，正在创建..."
    mkdir -p "$TARGET_DIR"
    if [ $? -ne 0 ]; then
        echo "错误：无法创建目标目录 $TARGET_DIR"
        exit 1
    fi
fi

# 获取源目录中的文件数量
FILE_COUNT=$(find "$SOURCE_DIR" -maxdepth 1 -type f | wc -l)

if [ $FILE_COUNT -eq 0 ]; then
    echo "警告：源目录 $SOURCE_DIR 中没有找到文件"
    exit 0
fi

echo "开始剪切 $FILE_COUNT 个文件从 $SOURCE_DIR 到 $TARGET_DIR..."

# 剪切所有文件
mv "$SOURCE_DIR"/* "$TARGET_DIR"/ 2>/dev/null

if [ $? -eq 0 ]; then
    echo "成功！已将所有文件从 $SOURCE_DIR 剪切到 $TARGET_DIR"
else
    echo "警告：部分文件可能未能成功剪切，请检查权限和文件状态"
fi

echo "操作完成。"
