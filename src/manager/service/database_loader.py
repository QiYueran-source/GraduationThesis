"""
数据库加载器  
"""
# 库
import datetime as dt
import pickle

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
from .exception import (
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
            factors_df = get_factors_data(code_list,factors_start_date,factors_end_date)
            return_df = get_stock_return(code_list,return_start_date,return_end_date)

            # 保存数据 
            self.client.set(
                name = REDIS_PREFIX_MANAGER.build_df_key(each_year,'factors_df'),
                value = pickle.dumps(factors_df.to_dicts()),
                ex=7200
            )
            self.client.set(
                name = REDIS_PREFIX_MANAGER.build_df_key(each_year,'return_df'),
                value = pickle.dumps(return_df.to_dicts()),
                ex=7200
            )  
            logger.info(f"处理数据加载请求: 加载{message['payload']['request_id']}的{each_year}年数据")

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
    

    def _subscribe_handlers(self):
        """注册处理器,构造时自动注册"""
        MESSAGE_BUS.subscribe('load_request', self.load_data_handler,'DatabaseLoader')

# 全局数据库加载器  
DATABASE_LOADER = DatabaseLoader()
