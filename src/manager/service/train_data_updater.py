"""
更新器  
1.有新的df加载后，转换为数据片，加载到redis
    - 数据标准化  
    - 数据补全  
2.保证redis中只有max_period期df，用于数据补全
"""
# 库
import polars as pl
import redis 

# 组件
from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR
from src.manager.database import read_factors_info, get_factors_data, get_factors_name, read_return

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[TrainDataUpdater]')

# 训练数据更新器  
class TrainDataUpdater:
    pass 

    def __init__(self):
        pass 

    #