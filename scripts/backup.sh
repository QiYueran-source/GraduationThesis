#!/usr/bin/env bash

set -euo pipefail

# 项目根目录（本脚本所在目录的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 目标备份目录（注意路径中有空格，需要用引号）
DEST_DIR="/mnt/e/大学事务/毕业论文"

# 创建目标目录
mkdir -p "${DEST_DIR}"

cd "${PROJECT_ROOT}"

# 复制项目根目录下的所有 .ipynb 文件（如果有的话）
shopt -s nullglob
ipynb_files=("${PROJECT_ROOT}"/*.ipynb)
if ((${#ipynb_files[@]} > 0)); then
  echo "开始复制 .ipynb 文件到：${DEST_DIR}"
  for f in "${ipynb_files[@]}"; do
    echo "  复制文件：${f}"
    cp -v "${f}" "${DEST_DIR}/"
  done
else
  echo "未找到需要备份的 .ipynb 文件"
fi
shopt -u nullglob

# 复制 result 目录（如果存在）
if [ -d "${PROJECT_ROOT}/result" ]; then
  echo "开始复制 result 目录到：${DEST_DIR}"
  cp -rv "${PROJECT_ROOT}/result" "${DEST_DIR}/"
else
  echo "未找到 result 目录，跳过复制"
fi

echo "备份完成：.ipynb 文件和 result 目录已复制到 ${DEST_DIR}"
