#!/bin/bash
# 解压日个股回报率 zip 文件到对应目录

# 设置路径
ZIP_DIR="/home/frank/files/programs/GraduationThesis/data/zip"
TARGET_DIR="/home/frank/files/programs/GraduationThesis/data/trade_data/local_data"

# 进入 zip 目录
cd "$ZIP_DIR" || exit 1

# 定义要处理的 zip 文件列表（排除已解压的 2020_2025）
ZIP_FILES=(
    "日个股回报率文件1997_2000.zip"
    "日个股回报率文件2000_2005.zip"
    "日个股回报率文件2005_2010.zip"
    "日个股回报率文件2010_2015.zip"
    "日个股回报率文件2015_2020.zip"
)

# 遍历每个 zip 文件
for zip_file in "${ZIP_FILES[@]}"; do
    if [ ! -f "$zip_file" ]; then
        echo "⚠️  文件不存在: $zip_file"
        continue
    fi
    
    # 从文件名提取目录名（去掉"文件"和".zip"）
    # 例如：日个股回报率文件1997_2000.zip -> 日个股回报率1997_2000
    dir_name=$(echo "$zip_file" | sed 's/日个股回报率文件/日个股回报率/' | sed 's/\.zip$//')
    target_path="$TARGET_DIR/$dir_name"
    
    echo "📦 正在解压: $zip_file"
    echo "📁 目标目录: $target_path"
    
    # 创建目标目录
    mkdir -p "$target_path"
    
    # 解压到目标目录
    unzip -q -o "$zip_file" -d "$target_path"
    
    if [ $? -eq 0 ]; then
        echo "✅ 解压成功: $dir_name"
        echo ""
    else
        echo "❌ 解压失败: $zip_file"
        echo ""
    fi
done

echo "🎉 所有文件解压完成！"