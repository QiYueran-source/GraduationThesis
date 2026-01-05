"""
数据库加载器  
"""
# 库
import polars as pl
import redis 
import datetime as dt
import yaml

# 组件
from src.manager.database import get_code_list, get_factors_info, get_stock_return
from src.manager.redis import REDIS_CONNECTOR
from src.manager.service.bus import MESSAGE_BUS
from src.manager.service.message import Message

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[DatabaseLoader]')

# 异常
from .exception import ServiceConfigurationException

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
        """处理初始化请求"""
        print(f"处理初始化请求: {message}")

    def _subscribe_handlers(self):
        """注册处理器"""
        MESSAGE_BUS.subscribe('init', self.init_handler)
        MESSAGE_BUS.subscribe('load_request', self.load_data_handler)

# 全局数据库加载器  
DATABASE_LOADER = DatabaseLoader()

