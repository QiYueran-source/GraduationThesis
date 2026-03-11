import polars as pl
import os
from pathlib import Path

# 1.读heter
heter = pl.read_ndjson('/home/frank/files/programs/GraduationThesis/empirical/heter/异质性_sum3.jsonl')

# 2.给定task_id，读取任务，找到其中与heter的portfolio和date相同的行 
TASK_ID = '20260225_1816_baseline1_1f77a8c2-c159-4769-ab53-4395774a51c7'
TASK_DIR = Path(f'/home/frank/files/programs/GraduationThesis/result/{TASK_ID}')

# 所有的节点
node_dirs = list[Path](TASK_DIR.iterdir())

# 获取其中performance_and_record_*.jsonl最多的节点
max_record_node = max(node_dirs, key=lambda x: len(list[Path](x.glob('performance_and_reward_*.jsonl'))))

# 获取jsonl路径列表
jsonl_paths = list[Path](max_record_node.glob('performance_and_reward_*.jsonl'))

# 读取jsonl
jsonl_data = pl.concat(pl.scan_ndjson(f) for f in jsonl_paths)

# 获取jsonl数据
print(jsonl_data.head().collect())