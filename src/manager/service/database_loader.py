"""
数据库加载器  
"""
# 库
import calendar
import datetime as dt
import json
import polars as pl
from typing import List, Literal

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
            factors_date_list = DatabaseLoader._generate_monthly_start_dates(each_year)
            return_date_list = DatabaseLoader._generate_monthly_start_dates(each_year) + DatabaseLoader._generate_monthly_start_dates(each_year + 1)[:1]  # 2月到次年1月
            factors_complete_primary_keys = DatabaseLoader._create_complete_dataframe(code_list, factors_date_list)
            return_complete_primary_keys = DatabaseLoader._create_complete_dataframe(code_list, return_date_list)

            # 获取实际数据
            factors_df = get_factors_data(code_list,factors_start_date,factors_end_date).with_columns(pl.col('accper').dt.strftime('%Y-%m-%d').alias('accper'))
            return_df = get_stock_return(code_list,return_start_date,return_end_date).with_columns(pl.col('accper').dt.strftime('%Y-%m-%d').alias('accper'))

            # 补充缺失的证券数据
            factors_df = DatabaseLoader._fill_missing_data(factors_df, factors_complete_primary_keys, "factors")
            return_df = DatabaseLoader._fill_missing_data(return_df, return_complete_primary_keys, "return")

            # 保存数据 
            try:
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
            except Exception as e:
                logger.error(f'保存df失败：{each_year}, {e}')
                raise Exception
                     
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

    @staticmethod
    def _generate_monthly_start_dates(year: int) -> List[str]:
        """生成指定年度的所有月份日期（月初日期，用于收益数据）"""
        dates = []
        for month in range(1, 13):
            date_str = f"{year}-{month:02d}-01"
            dates.append(date_str)
        return dates

    @staticmethod
    def _create_complete_dataframe(code_list: List[str], date_list: List[str]) -> pl.DataFrame:
        """创建包含所有(code, date)组合的完整DataFrame"""
        complete_data = []
        for code in code_list:
            for date in date_list:
                complete_data.append({"stkcd": code, "accper": date})
        all_primary_keys = pl.DataFrame(complete_data).with_columns(pl.col('stkcd').cast(pl.Utf8), pl.col('accper').cast(pl.Date))
        all_primary_keys = all_primary_keys.with_columns(
            pl.col('accper').dt.strftime('%Y-%m-%d').alias('accper')
        )
        return all_primary_keys

    @staticmethod
    def _fill_missing_data(df: pl.DataFrame, complete_primary_keys: pl.DataFrame, data_type:Literal['factors','return']) -> pl.DataFrame:
        """
        补充缺失的数据记录
        Args:
            df: 原始数据
            complete_primary_keys: 完整主键
            data_type: 数据类型
        用全主键与原始数据左连接，缺失的行用0填充
        Returns:
            pl.DataFrame: 补充缺失后的数据
        """
        # 左连接
        if df.height != complete_primary_keys.height:
            logger.warning(f"原始数据和完整主键高度不一致，原始数据高度: {df.height}, 完整主键高度: {complete_primary_keys.height}")
        filled_df = complete_primary_keys.join(df, on=['stkcd', 'accper'], how='left')
        return filled_df
        

    def _subscribe_handlers(self):
        """注册处理器,构造时自动注册"""
        MESSAGE_BUS.subscribe('load_request', self.load_data_handler,'DatabaseLoader')

# 全局数据库加载器  
DATABASE_LOADER = DatabaseLoader()
