"""
获取回报率  
"""
# 库
import datetime as dt
import polars as pl
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Dict, Any, List

# 组件
from src.manager.database.connection import (
    CONNECTION_URL,
    PARTITION_NUM,
    ENGINE,
    CONNECTION_POOL,
    BATCH_SIZE,
    MAX_WORKERS
)

# 异常
from src.manager.database.exception import (
    DatabaseException,
    DatabaseReadException
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[FactorsDatabase]')


# 读取因子数据库
def read_return(
    code_list: List[str],
    start_date: dt.date,
    end_date: dt.date,
)->pl.DataFrame:
    '''读取回报率'''
    code_list_with_quotes = [f"'{code}'" for code in code_list]
    query = f"""
        SELECT *
        FROM trade_data.monthly_return
        WHERE stkcd IN ({', '.join(code_list_with_quotes)})
        AND accper BETWEEN '{start_date}' AND '{end_date}'
    """
    try:
        monthly_return = pl.read_database_uri(
            uri=CONNECTION_URL,
            query=query,
            engine=ENGINE,
            partition_on='accper',
            partition_num=PARTITION_NUM,
        )
        return monthly_return
    except Exception as e:
        logger.error(f"读取回报率失败: {e}")
        raise DatabaseReadException(f"读取回报率失败: {e}")
    