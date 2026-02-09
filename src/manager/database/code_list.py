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

def get_code_list(
    code_type: Literal['test', 'all'],
    quality_threshold: float = None
) -> List[str]:
    if code_type == 'test':
        return ['000001','000002','000004','000005','000006','000007','000008','000009','000010']
    elif code_type == 'all':
        return _get_all_codes_with_quality_check(quality_threshold)
    else:
        raise NotImplementedError(f"Unsupported code_type: {code_type}")


def _get_all_codes_with_quality_check(quality_threshold: float = None) -> List[str]:
    """获取所有符合数据质量要求的证券代码"""

    # 1. 读取配置文件
    try:
        with open('src/config/hyparam.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise

    # 2. 获取时间范围和质量阈值
    meta_config = config.get('meta', {})
    stock_pool_config = config.get('stock_pool', {})

    start_year, start_month = meta_config.get('earliest_year_month', [1997, 1])
    end_year = meta_config.get('end_year', 2024)

    # 使用参数传入的阈值，如果没有则使用配置文件中的默认值
    if quality_threshold is None:
        quality_threshold = stock_pool_config.get('data_quality_threshold', 0.8)

    # 3. 计算总月数
    total_months = _calculate_total_months(start_year, start_month, end_year)

    logger.info(f"时间范围: {start_year}-{start_month:02d} 到 {end_year}-12")
    logger.info(f"总月数: {total_months}, 质量阈值: {quality_threshold}")

    # 4. 查询数据质量统计（直接从monthly_return表计算）
    try:
        # 构建时间范围条件
        start_date = f"{start_year}-{start_month:02d}-01"
        end_date = f"{end_year}-12-31"

        query = f"""
        WITH monthly_stats AS (
            SELECT
                stkcd,
                COUNT(*)::integer as actual_months,
                {total_months}::integer as total_months,
                (COUNT(*) * 1.0 / {total_months})::float8 as completeness_ratio
            FROM trade_data.monthly_return
            WHERE accper BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY stkcd
        )
        SELECT
            stkcd::text,
            actual_months::integer,
            total_months::integer,
            completeness_ratio::float8
        FROM monthly_stats
        WHERE completeness_ratio >= {quality_threshold}
        ORDER BY stkcd
        """

        df = pl.read_database_uri(
            uri=CONNECTION_URL,
            query=query,
            engine=ENGINE,
        )

        codes = df['stkcd'].to_list()
        logger.info(f"找到 {len(codes)} 只符合条件的证券 (质量阈值: {quality_threshold})")

        return codes

    except Exception as e:
        logger.error(f"查询证券列表失败: {e}")
        raise


def _calculate_total_months(start_year: int, start_month: int, end_year: int) -> int:
    """计算从起始年月到结束年份12月的总月数"""
    total_months = 0

    if start_year == end_year:
        # 同一年
        total_months = 13 - start_month
    else:
        # 起始年剩余月数
        total_months += 13 - start_month
        # 中间完整年数
        total_months += (end_year - start_year - 1) * 12
        # 结束年12个月
        total_months += 12

    return total_months 