from huggingface_hub import snapshot_download
import os

# 设置 HuggingFace 镜像端点
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用 HuggingFace 镜像

# 指定本地保存路径
local_dir = "~/llm/Qwen2.5-1.5B"
model_name = "Qwen/Qwen2.5-1.5B"

# 下载整个仓库（包括所有文件）
print(f"开始下载模型仓库: {model_name}")
print(f"使用镜像: {os.environ.get('HF_ENDPOINT', 'https://huggingface.co')}")
snapshot_download(
    repo_id=model_name,
    local_dir=local_dir,
    local_dir_use_symlinks=False,  # 不使用符号链接，直接复制
    resume_download=True            # 支持断点续传
)

print(f"模型已下载到: {local_dir}")