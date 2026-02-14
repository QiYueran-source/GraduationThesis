"""
证券列表加载
"""
import calendar
from typing import Literal, List
import polars as pl
import yaml

# 组件
from src.manager.database.connection import (
    CONNECTION_URL,
    ENGINE,
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[CodeList]')

# 读取配置
try:
    with open('src/config/hyparam.yaml', 'r', encoding = 'utf-8') as f:
        stock_pool_config = yaml.safe_load(f).get('stock_pool', {})
        stock_pool_type = stock_pool_config.get('pool_type', 'test')
        stock_pool_data_filter = stock_pool_config.get('data_filter', {})
        stock_pool_data_quality_threshold = stock_pool_config.get('data_quality_threshold', 0.8)
except Exception as e:
    logger.error(f"配置读取异常: {e}, 使用默认配置")
    stock_pool_type = 'test'
    stock_pool_data_filter = {}
    stock_pool_data_quality_threshold = 0.8

def get_code_list(**kwargs) -> List[str]:
    # 接收参数
    pool_type = stock_pool_type
    data_filter = stock_pool_data_filter
    data_quality_threshold = stock_pool_data_quality_threshold

    # 1 
    return ['000001', '000002', '000003', '000004', '000005', '000006', '000007', '000008', '000009', '000010']


