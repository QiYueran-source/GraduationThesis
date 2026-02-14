"""
证券列表加载
"""
import json
from typing import List, Optional
import polars as pl
import yaml

# 组件
from src.manager.database.connection import (
    CONNECTION_URL,
    ENGINE,
)
from src.manager.redis import REDIS_CONNECTOR, REDIS_PREFIX_MANAGER

# 异常
from src.manager.database.exception import DatabaseReadException

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[CodeList]')

# 读取配置（stock_pool + meta，供 read_db_to_get_code_list 使用）
try:
    with open('src/config/hyparam.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}
    stock_pool_config = config.get('stock_pool', {})
    stock_pool_type = stock_pool_config.get('pool_type', 'test')
    stock_pool_data_filter = stock_pool_config.get('data_filter', {})
    stock_pool_data_quality_threshold = stock_pool_config.get('data_quality_threshold', 0.8)
    meta_config = config.get('meta', {})
    meta_start_year = int(meta_config.get('start_year', 1997))
    meta_end_year = int(meta_config.get('end_year', 2024))
except Exception as e:
    logger.error(f"配置读取异常: {e}, 使用默认配置")
    stock_pool_type = 'test'
    stock_pool_data_filter = {}
    stock_pool_data_quality_threshold = 0.8
    meta_config = {}
    meta_start_year, meta_end_year = 1997, 2024

def _get_all_code_list() -> List[str]:
    """
    获取所有股票代码列表
    来自 statics.public_code_in_both_factors_and_return 视图
    返回 stkcd 列的所有证券代码列表
    """
    query = """
        SELECT DISTINCT stkcd
        FROM statics.public_code_in_both_factors_and_return
        ORDER BY stkcd
    """
    try:
        df = pl.read_database_uri(
            uri=CONNECTION_URL,
            query=query,
            engine=ENGINE,
        )
        return df['stkcd'].cast(pl.Utf8).to_list()
    except Exception as e:
        logger.error(f"读取证券列表失败: {e}")
        raise DatabaseReadException(f"读取证券列表失败: {e}")

def _get_return_stats(
    stkcd_list: Optional[List[str]] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> pl.DataFrame:
    """
    从 statics.monthly_return_stats 视图获取回报率统计信息。
    可选：仅返回 stkcd 在 stkcd_list 中，且 earliest 年份 <= start_year、latest_return_date >= end_year-12-31 的行（用于 balance 筛选）。
    """
    query = "SELECT stkcd, earliest_return_date, latest_return_date, total_months, valid_returns, null_returns, expected_months, data_completeness_pct FROM statics.monthly_return_stats"
    conditions = []
    if stkcd_list:
        placeholders = ", ".join(f"'{c}'" for c in stkcd_list)
        conditions.append(f"stkcd IN ({placeholders})")
    if start_year is not None:
        conditions.append(f"EXTRACT(YEAR FROM earliest_return_date)::integer <= {int(start_year)}")
    if end_year is not None:
        conditions.append(f"latest_return_date >= '{int(end_year)}-12-31'::date")
    if conditions:
        query = query + " WHERE " + " AND ".join(conditions)
    query = query + " ORDER BY stkcd"
    try:
        df = pl.read_database_uri(
            uri=CONNECTION_URL,
            query=query,
            engine=ENGINE,
        )
        return df
    except Exception as e:
        logger.error(f"读取 monthly_return_stats 失败: {e}")
        raise DatabaseReadException(f"读取 monthly_return_stats 失败: {e}")

def _get_fin_code_list() -> List[str]:
    """
    获取金融股票代码列表
    来自 statics.fin_co 视图
    返回 stkcd 列的所有金融股票代码列表
    """
    query = """
        SELECT DISTINCT stkcd
        FROM statics.fin_co
        ORDER BY stkcd
    """
    try:
        df = pl.read_database_uri(
            uri=CONNECTION_URL,
            query=query,
            engine=ENGINE,
        )
        return df['stkcd'].cast(pl.Utf8).to_list()
    except Exception as e:
        logger.error(f"读取金融证券列表失败: {e}")
        raise DatabaseReadException(f"读取金融证券列表失败: {e}")


def _get_st_code_list() -> List[str]:
    """
    获取 ST 股票代码列表
    来自 statics.st_co 视图
    返回 stkcd 列的所有 ST 股票代码列表
    """
    query = """
        SELECT DISTINCT stkcd
        FROM statics.st_co
        ORDER BY stkcd
    """
    try:
        df = pl.read_database_uri(
            uri=CONNECTION_URL,
            query=query,
            engine=ENGINE,
        )
        return df['stkcd'].cast(pl.Utf8).to_list()
    except Exception as e:
        logger.error(f"读取 ST 证券列表失败: {e}")
        raise DatabaseReadException(f"读取 ST 证券列表失败: {e}")


def read_db_to_get_code_list() -> List[str]:
    """
    从数据库中读取股票代码列表并写入 Redis
    """
    # 接收参数
    pool_type = stock_pool_type
    data_filter = stock_pool_data_filter
    data_quality_threshold = stock_pool_data_quality_threshold

    # test 池，测试用
    if pool_type == 'test':
        return ['000001', '000002', '000003', '000004', '000005', '000006', '000007', '000008', '000009', '000010']
    
    # 全市场池，全市场股票
    all_code_list = _get_all_code_list()
    result_code_list = None
    if pool_type == 'all':
        result_code_list = all_code_list
    elif pool_type == 'balance':
        df = _get_return_stats(stkcd_list=all_code_list, start_year=meta_start_year, end_year=meta_end_year)
        balance_code_list = df['stkcd'].cast(pl.Utf8).to_list()
        result_code_list = balance_code_list
    elif pool_type == 'clean':
        # 在 all 上按数据完整度筛选
        df = _get_return_stats()
        threshold_pct = data_quality_threshold * 100
        df = df.filter(pl.col('data_completeness_pct') >= threshold_pct)
        result_code_list = df['stkcd'].cast(pl.Utf8).to_list()
    elif pool_type == 'balance_and_clean':
        # 在 balance 上按数据完整度筛选
        df = _get_return_stats(start_year=meta_start_year, end_year=meta_end_year)
        threshold_pct = data_quality_threshold * 100
        df = df.filter(pl.col('data_completeness_pct') >= threshold_pct)
        result_code_list = df['stkcd'].cast(pl.Utf8).to_list()
    else:
        raise ValueError(f"不支持的 pool_type: {pool_type}，可选: test, all, balance, clean, balance_and_clean")

    # 过滤 
    if data_filter.get('exclude_st', False):
        st_code_list = _get_st_code_list()
        result_code_list = [code for code in result_code_list if code not in st_code_list]
    if data_filter.get('exclude_fin', False):
        fin_code_list = _get_fin_code_list()
        result_code_list = [code for code in result_code_list if code not in fin_code_list]


    return result_code_list

def get_code_list(**kwargs) -> List[str]:
    """从 Redis meta 中获取股票代码列表；若无 meta 或 stock_list 则回退到 read_db_to_get_code_list()"""
    client = REDIS_CONNECTOR.get_client()
    meta_key = REDIS_PREFIX_MANAGER.build_meta_key()
    raw = client.get(meta_key)
    if raw:
        try:
            meta = json.loads(raw)
            stock_list = meta.get('stock_list')
            if stock_list and isinstance(stock_list, list):
                return list(stock_list)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"解析 meta 失败: {e}，回退到 read_db_to_get_code_list")
    return read_db_to_get_code_list()

