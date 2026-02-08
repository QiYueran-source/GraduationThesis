"""
数据库加载器  
"""
# 库
import calendar
import datetime as dt
import json
import polars as pl
from typing import List

# 组件
from src.manager.database import get_code_list, get_factors_data, get_factors_info, get_stock_return
from src.manager.redis import REDIS_CONNECTOR, REDIS_PREFIX_MANAGER
from src.manager.service.bus import MESSAGE_BUS
from src.manager.service.message import (
    Message,
    DataLoadedMessage,DataLoadedPayload
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[DatabaseLoader]')

# 异常
from src.manager.service.exception import (
    ServiceConfigurationException,
    ServiceException
)

# 数据库加载器  
class DatabaseLoader:
    def __init__(
        self
    ):  
        # redis客户端
        self.client = REDIS_CONNECTOR.get_client()

        # 注册处理器
        self._subscribe_handlers()
    
    def load_data_handler(self, message: Message):
        """处理数据加载请求"""
        # 加载消息  
        stock_pool = message['payload']['stock_pool']
        year_list = message['payload']['year_list']
        for each_year in year_list:
            # 加载数据
            code_list = get_code_list(code_type = stock_pool)
            factors_start_date = dt.date(each_year,1,1)
            factors_end_date = dt.date(each_year,12,31)
            return_start_date = dt.date(each_year,2,1)
            return_end_date = dt.date(each_year+1,1,31)

            # 生成完整的数据框架（所有code和date的组合）
            factors_date_list = self._generate_monthly_dates(each_year)
            return_date_list = self._generate_monthly_dates(each_year) + self._generate_monthly_dates(each_year + 1)[:1]  # 2月到次年1月
            factors_complete_df = self._create_complete_dataframe(code_list, factors_date_list)
            return_complete_df = self._create_complete_dataframe(code_list, return_date_list)

            # 获取实际数据
            factors_df = get_factors_data(code_list,factors_start_date,factors_end_date).with_columns(pl.col('accper').dt.strftime('%Y-%m-%d').alias('accper'))
            return_df = get_stock_return(code_list,return_start_date,return_end_date).with_columns(pl.col('accper').dt.strftime('%Y-%m-%d').alias('accper'))

            # 补充缺失的证券数据
            factors_df = self._fill_missing_data(factors_df, factors_complete_df, "因子")
            return_df = self._fill_missing_data(return_df, return_complete_df, "回报")
    
            # 保存数据 
            self.client.set(
                name = REDIS_PREFIX_MANAGER.build_df_key(each_year,'factors_df'),
                value = json.dumps(factors_df.to_dicts()),
                ex=7200
            )
            self.client.set(
                name = REDIS_PREFIX_MANAGER.build_df_key(each_year,'return_df'),
                value = json.dumps(return_df.to_dicts()),
                ex=7200
            )  
            logger.info(f"处理数据加载请求: 加载请求{message['payload']['request_id']}的{each_year}年数据")

            # 发布数据加载完成事件
            payload = DataLoadedPayload(
                request_id=message['payload']['request_id'],
                year=each_year
            )
            data_loaded_message = DataLoadedMessage(
                message_type='data_loaded',
                publisher='DatabaseLoader',
                payload=payload
            )
            MESSAGE_BUS.publish(
                message = data_loaded_message
            )
            logger.info(f"发布数据加载完成事件: {payload}")


    def _generate_monthly_dates(self, year: int) -> List[str]:
        """生成指定年度的所有月份日期（月末日期）"""
        dates = []
        for month in range(1, 13):
            # 使用月末日期作为会计期间
            last_day = calendar.monthrange(year, month)[1]
            date_str = f"{year}-{month:02d}-{last_day:02d}"
            dates.append(date_str)
        return dates

    def _create_complete_dataframe(self, code_list: List[str], date_list: List[str]) -> pl.DataFrame:
        """创建包含所有(code, date)组合的完整DataFrame"""
        complete_data = []
        for code in code_list:
            for date in date_list:
                complete_data.append({"stkcd": code, "accper": date})

        return pl.DataFrame(complete_data)

    def _fill_missing_data(self, df: pl.DataFrame, complete_df: pl.DataFrame, data_type: str) -> pl.DataFrame:
        """补充缺失的数据记录"""
        if df.is_empty():
            logger.warning(f"{data_type} 数据为空，使用完整框架")
            # 为完整框架添加数据列（填充默认值）
            filled_df = complete_df
            if data_type == "因子":
                # 为因子数据添加列，默认填充0
                filled_df = filled_df.with_columns([
                    pl.lit(0.0).alias(col) for col in df.columns if col not in ['stkcd', 'accper']
                ])
            elif data_type == "回报":
                # 为回报数据添加列，默认填充0（或NaN，根据需求调整）
                filled_df = filled_df.with_columns([
                    pl.lit(0.0).alias(col) for col in df.columns if col not in ['stkcd', 'accper']
                ])
            return filled_df

        # 左连接，确保所有(code, date)组合都存在
        filled_df = complete_df.join(
            df,
            on=["stkcd", "accper"],
            how="left"
        )

        # 填充缺失的数值列
        if data_type == "因子":
            # 因子数据用0填充
            numeric_cols = [col for col in df.columns if col not in ['stkcd', 'accper'] and df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]
            if numeric_cols:
                filled_df = filled_df.with_columns([
                    pl.col(col).fill_null(0.0).alias(col) for col in numeric_cols
                ])
        elif data_type == "回报":
            # 回报数据用0填充（可以根据需求改为NaN: pl.lit(float('nan')))
            numeric_cols = [col for col in df.columns if col not in ['stkcd', 'accper'] and df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]
            if numeric_cols:
                filled_df = filled_df.with_columns([
                    pl.col(col).fill_null(0.0).alias(col) for col in numeric_cols
                ])

        # 统计补充的数据量
        original_count = len(df)
        filled_count = len(filled_df)
        added_count = filled_count - original_count

        if added_count > 0:
            logger.info(f"{data_type} 数据补全：原始{original_count}条，补充后{filled_count}条，新增{added_count}条记录")

        return filled_df

    def _subscribe_handlers(self):
        """注册处理器,构造时自动注册"""
        MESSAGE_BUS.subscribe('load_request', self.load_data_handler,'DatabaseLoader')

# 全局数据库加载器  
DATABASE_LOADER = DatabaseLoader()
