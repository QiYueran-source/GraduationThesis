"""
数据库加载器  
"""
# 库
import polars as pl
import redis 
import datetime as dt
import yaml
import dateutil
import pickle

# 组件
from src.manager.database import get_code_list, get_factors_data, get_factors_info, get_stock_return
from src.manager.redis import REDIS_CONNECTOR, REDIS_PREFIX_MANAGER
from src.manager.service.bus import MESSAGE_BUS
from src.manager.service.message import (
    Message,
    InitMessagePayload,
    InitDataLoadedPayload,
    InitDataLoadedMessage,
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
        self._config = {}

        # 加载配置
        self._load_config()

        # 获取参数  
        _phase_param = self._phase_param()
        self.code_list = get_code_list(_phase_param['stock_pool'], _phase_param['data_quality_threshold'])
        self.start_date = _phase_param['start_date']
        self.max_periods = _phase_param['max_periods']

        # 注册处理器
        self._subscribe_handlers()

    def _load_config(self):
        # 加载配置
        try:
            with open('src/config/hyparam.yaml', 'r', encoding = 'utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise ServiceConfigurationException(f"加载配置失败: {e}")
    
    def _phase_param(self)->dict:
        stock_pool = self._config['train']['stock_pool']
        data_quality_threshold = self._config['train']['data_quality_threshold']
        start_date = self._config['train']['start_date']
        max_periods = self._config['train']['window_size'] + self._config['redis_redundancy']['max_periods_adder']
        
        return {
            'stock_pool': stock_pool,
            'data_quality_threshold': data_quality_threshold,
            'start_date': start_date,
            'max_periods': max_periods
        }

    def load_data_handler(self, message: Message):
        """处理数据加载请求"""
        print(f"处理数据加载请求: {message['id']}")
    
    def init_handler(self, message: Message = None):
        """处理初始化请求  
        message: InitMessage  
        payload: InitMessagePayload 
        从数据库加载初始数据  
        根据start_date和max_periods，查询数据库，获取初始数据，以polars.DataFrame形式保存redis
        然后发布InitDataLoadedMessage，payload: DataLoadedPayload
        """
        print(f"处理初始化请求: {message}")  
        req_id = message['payload']['req_id'] # "获取req_id"

        try:
            # 获取Redis客户端
            client = REDIS_CONNECTOR.get_client()

            # 从数据库加载初始数据
            end_date = self.start_date + dateutil.relativedelta.relativedelta(months=self.max_periods)
            factors_df = get_factors_data(self.code_list, self.start_date, end_date)
            return_df = get_stock_return(self.code_list, self.start_date, end_date)
            factors_data = pickle.dumps(factors_df)
            return_data = pickle.dumps(return_df)

            # 构建数据
            init_factors_df_key = REDIS_PREFIX_MANAGER.build_init_factors_df_key(self.start_date.year)
            init_return_df_key = REDIS_PREFIX_MANAGER.build_init_return_df_key(self.start_date.year)
            
            # 缓存数据
            client.set(init_factors_df_key, factors_data)
            client.set(init_return_df_key, return_data)
            
            # 发布InitDataLoadedMessage，payload: DataLoadedPayload
            MESSAGE_BUS.publish(InitDataLoadedMessage(
                publisher='database_loader',
                payload=InitDataLoadedPayload(
                    req_id=req_id
                )
            ))
            logger.info(f"初始化数据加载完成: {req_id}")
            
        except Exception as e:
            logger.error(f"加载初始数据失败: {e}")
            raise ServiceException(f"加载初始数据失败: {e}")
        

    def _subscribe_handlers(self):
        """注册处理器,构造时自动注册"""
        MESSAGE_BUS.subscribe('init', self.init_handler)
        MESSAGE_BUS.subscribe('load_request', self.load_data_handler)

# 全局数据库加载器  
DATABASE_LOADER = DatabaseLoader()

