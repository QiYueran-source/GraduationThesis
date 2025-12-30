# 🤗Huggingface Model Downloader

> [!Note]  
> ***(2025-01-08)*** Add feature for 🏷️**Tag(***Revision***) Selection**, contributed by [@Bamboo-D](https://gist.github.com/Bamboo-D/8875a46c8d201af221b631f1936f6fff).  
> ***(2024-12-17)*** Add feature for ⚡**Quick Startup** and ⏭️**Fast Resume**, enabling skipping of downloaded files, while removing the `git clone` dependency to accelerate file list retrieval.  

Considering the lack of multi-threaded download support in the official [`huggingface-cli`](https://huggingface.co/docs/huggingface_hub/guides/download#download-from-the-cli), and the inadequate error handling in [`hf_transfer`](https://github.com/huggingface/hf_transfer), This command-line tool leverages `curl` and `aria2c` for fast and robust downloading of models and datasets.

## Features
- ⏯️ **Resume from breakpoint**: You can re-run it or Ctrl+C anytime.
- 🚀 **Multi-threaded Download**: Utilize multiple threads to speed up the download process.
- 🚫 **File Exclusion**: Use `--exclude` or `--include` to skip or specify files, save time for models with **duplicate formats** (e.g., `*.bin` or `*.safetensors`).
- 🔐 **Auth Support**: For gated models that require Huggingface login, use `--hf_username` and `--hf_token` to authenticate.
- 🪞 **Mirror Site Support**: Set up with `HF_ENDPOINT` environment variable.
- 🌍 **Proxy Support**: Set up with `https_proxy` environment variable.
- 📦 **Simple**: Minimal dependencies, requires only `curl` and `wget`, while `aria2` and `jq` are optional for better performance.
- 🏷️ **Tag Selection**: Support downloading specific model/dataset revision using `--revision`.

## Usage
First, Download [`hfd.sh`](#file-hfd-sh) or clone this repo, and then grant execution permission to the script.
```bash
chmod a+x hfd.sh
```

you can create an alias for convenience
```bash
alias hfd="$PWD/hfd.sh"
```

**Usage Instructions**
```
$ ./hfd.sh --help
Usage:
  hfd <REPO_ID> [--include include_pattern1 include_pattern2 ...] [--exclude exclude_pattern1 exclude_pattern2 ...] [--hf_username username] [--hf_token token] [--tool aria2c|wget] [-x threads] [-j jobs] [--dataset] [--local-dir path] [--revision rev]

Description:
  Downloads a model or dataset from Hugging Face using the provided repo ID.

Arguments:
  REPO_ID         The Hugging Face repo ID (Required)
                  Format: 'org_name/repo_name' or legacy format (e.g., gpt2)
Options:
  include/exclude_pattern The patterns to match against file path, supports wildcard characters.
                  e.g., '--exclude *.safetensor *.md', '--include vae/*'.
  --include       (Optional) Patterns to include files for downloading (supports multiple patterns).
  --exclude       (Optional) Patterns to exclude files from downloading (supports multiple patterns).
  --hf_username   (Optional) Hugging Face username for authentication (not email).
  --hf_token      (Optional) Hugging Face token for authentication.
  --tool          (Optional) Download tool to use: aria2c (default) or wget.
  -x              (Optional) Number of download threads for aria2c (default: 4).
  -j              (Optional) Number of concurrent downloads for aria2c (default: 5).
  --dataset       (Optional) Flag to indicate downloading a dataset.
  --local-dir     (Optional) Directory path to store the downloaded data.
                             Defaults to the current directory with a subdirectory named 'repo_name'
                             if REPO_ID is is composed of 'org_name/repo_name'.
  --revision      (Optional) Model/Dataset revision to download (default: main).

Example:
  hfd gpt2
  hfd bigscience/bloom-560m --exclude *.bin *.msgpack onnx/*
  hfd meta-llama/Llama-2-7b --hf_username myuser --hf_token mytoken -x 4
  hfd lavita/medical-qa-shared-task-v1-toy --dataset
  hfd bartowski/Phi-3.5-mini-instruct-exl2 --revision 5_0
```
**Download a model**
```
hfd bigscience/bloom-560m
```

**Download a model need login**

Get huggingface token from [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), then
```bash
hfd meta-llama/Llama-2-7b --hf_username YOUR_HF_USERNAME_NOT_EMAIL --hf_token YOUR_HF_TOKEN
```
**Download a model and exclude certain files (e.g., .safetensors)**


```bash
hfd bigscience/bloom-560m --exclude *.bin *.msgpack onnx/*
```
You can also exclude multiple pattern like that
```bash
hfd bigscience/bloom-560m --exclude *.bin --exclude *.msgpack --exclude onnx/*
```

**Download specific files using include patterns**
```bash
hfd Qwen/Qwen2.5-Coder-32B-Instruct-GGUF --include *q2_k*.gguf
```

**Download a dataset**
```bash
hfd lavita/medical-qa-shared-task-v1-toy --dataset
```

**Download a specific revision of a model**
```bash
hfd bartowski/Phi-3.5-mini-instruct-exl2 --revision 5_0
```

**Multi-threading and Parallel Downloads**

The script supports two types of parallelism when using `aria2c`:

- **Threads per File (`-x`)**: Controls connections per file, usage: `hfd gpt2 -x 8`, recommended: 4-8, default: 4 threads.

- **Concurrent Files (`-j`)**: Controls simultaneous file downloads, usage: `hfd gpt2 -j 3`, recommended: 3-8, default: 5 files. 

Combined usage:
```bash
hfd gpt2 -x 8 -j 3  # 8 threads per file, 3 files at once
```
