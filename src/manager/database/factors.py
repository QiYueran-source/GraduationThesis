'''
因子数据库管理
'''
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

def _query_single_table(table_name: str, date_condition: str, code_condition: str) -> tuple[str, pl.DataFrame]:
    """查询单个表的函数（用于并行执行）"""
    try:
        # 构建查询：获取该表的所有数据
        query = f"""
            SELECT *
            FROM {table_name}
            WHERE {date_condition} {code_condition}
        """

        # 执行查询
        table_data = pl.read_database_uri(
            uri=CONNECTION_URL,
            partition_on='accper',
            partition_num=PARTITION_NUM,
            query=query,
            engine=ENGINE
        )

        logger.debug(f"表 {table_name} 获取到 {len(table_data)} 条记录")
        return table_name, table_data

    except Exception as e:
        logger.error(f"查询表 {table_name} 失败: {e}")
        raise DatabaseReadException(f"查询表 {table_name} 失败: {e}")

# 读取因子数据库
def read_factors_info()->pl.DataFrame:
    '''读取因子数据库'''
    query_factors_metainfo = """
        SELECT * FROM factors_data.factor_metadata
    """ 

    schema_overrides = {
        # 字符串字段 - Polars 会自动推断为 Utf8，但可以明确指定
        "factor_name": pl.Utf8,      # VARCHAR(50) NOT NULL
        "full_name": pl.Utf8,        # VARCHAR(100)
        "chinese_name": pl.Utf8,     # VARCHAR(100)  
        "category": pl.Utf8,         # VARCHAR(50)
        "construction": pl.Utf8,     # TEXT
        "time_range": pl.Utf8,       # VARCHAR(200)
        "frequency": pl.Utf8,        # VARCHAR(100)
        "table_name": pl.Utf8,       # VARCHAR(100)
        
        # 时间戳字段 - 建议明确指定以确保正确解析
        "created_at": pl.Datetime    # TIMESTAMP WITHOUT TIME ZONE
    }

    try:
        factors_metainfo = pl.read_database_uri(
            query = query_factors_metainfo,
            uri = CONNECTION_URL,
            schema_overrides = schema_overrides
        )
        return factors_metainfo
    except Exception as e:
        logger.error(f"读取因子数据库失败: {e}")
        raise DatabaseReadException(f"读取因子数据库失败: {e}")

def get_factors_name()->List[str]:
    '''获取因子名称'''
    factors_name = read_factors_info()['factor_name'].to_list()
    return factors_name

def get_factors_data(
    code_list: List[str],
    start_date: dt.date,
    end_date: dt.date,
) -> pl.DataFrame:
    '''获取指定日期范围内指定证券的所有因子数据

    Args:
        code_list: 证券代码列表，空列表表示获取所有证券
        start_date: 开始日期（包含）
        end_date: 结束日期（包含）

    Returns:
        pl.DataFrame: 宽表格式的因子数据，每行包含：
        - stkcd: 证券代码
        - accper: 会计期间
        - [各种因子列]: 该表的因子值
        - table_name: 数据来源表名（用于区分不同类别因子）
    '''

    try:
        # 1. 获取所有因子表信息
        factors_meta = read_factors_info()
        table_names = factors_meta['table_name'].unique().to_list()

        logger.info(f"开始获取因子数据，共 {len(table_names)} 个因子表")

        # 2. 构建查询条件
        date_condition = f"accper BETWEEN '{start_date}' AND '{end_date}'"

        if code_list:
            code_list_str = ', '.join(f"'{code}'" for code in code_list)
            code_condition = f"AND stkcd IN ({code_list_str})"
        else:
            code_condition = ""

        # 3. 并行查询所有因子表
        all_factors_data = []
        effective_workers = min(len(table_names), MAX_WORKERS)

        logger.info(f"使用 {effective_workers} 个线程并行查询 {len(table_names)} 个因子表")

        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            # 提交所有查询任务
            future_to_table = {
                executor.submit(_query_single_table, table_name, date_condition, code_condition): table_name
                for table_name in table_names
            }

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_table):
                table_name = future_to_table[future]
                try:
                    result_table_name, table_data = future.result()
                    if len(table_data) > 0:
                        all_factors_data.append(table_data)
                    else:
                        logger.debug(f"表 {result_table_name} 无符合条件的数据")
                except Exception as e:
                    logger.error(f"处理表 {table_name} 结果时出错: {e}")
                    # 可以选择继续或中断，这里选择继续
                    continue

        # 4. 合并所有数据
        if not all_factors_data:
            logger.warning("没有找到任何因子数据")
            return pl.DataFrame()
    
        # 使用 join 基于 (stkcd, accper) 合并
        combined_df = all_factors_data[0]  # 起始DataFrame

        for df in all_factors_data[1:]:
            combined_df = combined_df.join(
                df,
                on=["stkcd", "accper"],  # 连接键
                how="outer"  # 外连接，保留所有数据
            ).drop(['stkcd_right', 'accper_right'])
            
        logger.info(f"成功获取因子数据，共 {len(combined_df)} 条记录，{len(combined_df.columns)} 个列")
        return combined_df

    except Exception as e:
        logger.error(f"获取因子数据失败: {e}")
        raise DatabaseReadException(f"获取因子数据失败: {e}")
