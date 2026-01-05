"""
数据库读取线程  
1.读取数据库  
2.通过消息队列传递数据  
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