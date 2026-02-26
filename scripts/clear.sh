#!/bin/bash
# 清理端口池：调用与 NodeManager.clear_ports 相同的 DELETE 接口，将已分配端口移回可用队列。
# 配置从 src/config/node.yaml 的 web.ms_clear_host / ms_clear_port / ms_clear_url 读取。
# 请在项目根目录下执行，或脚本会自动切换到脚本所在目录的上一级（项目根）。

cd "$(dirname "$0")/.." || exit 1

python3 -c "
import sys
import yaml
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

config_path = Path('src/config/node.yaml')
if not config_path.exists():
    print('未找到 src/config/node.yaml')
    sys.exit(1)

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

web = config.get('web', {})
host = web.get('ms_clear_host', '43.139.192.176')
port = web.get('ms_clear_port', 8190)
path = web.get('ms_clear_url', '/clear')
url = f'http://{host}:{port}{path}'

req = Request(url, method='DELETE')
try:
    with urlopen(req, timeout=10) as resp:
        print('清理端口池成功')
        sys.exit(0)
except HTTPError as e:
    print(f'清理端口池失败 HTTP {e.code}: {e.reason}')
    sys.exit(1)
except URLError as e:
    print('清理端口池失败:', e.reason)
    sys.exit(1)
except Exception as e:
    print('清理端口池失败:', e)
    sys.exit(1)
"
