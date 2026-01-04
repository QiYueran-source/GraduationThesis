"""
数据库连接管理
"""
# 库
import os 
import dotenv
import polars as pl  
import yaml

# 异常
from src.manager.database.exception import (
    DatabaseException,
    ConfigReadException,
    EnvironmentVariableReadException
)

# 日志 
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[DatabaseConnection]')

# 读取env 
dotenv.load_dotenv()

# 读取配置文件
try:
    with open('src/config/database.yaml', 'r', encoding = 'utf-8') as f:
        DATABASE_CONFIG = yaml.safe_load(f)
        connection_pool = DATABASE_CONFIG.get('connection_pool', 10)
        batch_size = DATABASE_CONFIG.get('batch_size', 10000)
        partition_num = DATABASE_CONFIG.get('partition_num', 4)
        engine = DATABASE_CONFIG.get('engine', 'adbc')
        max_workers = DATABASE_CONFIG.get('max_workers', 10)
except Exception as e:
    logger.warning(f"配置读取异常: {e}, 使用默认配置")
    connection_pool = 10
    batch_size = 10000
    partition_num = 4
    engine = 'adbc'
    max_workers = 10

# 设置数据库连接参数
CONNECTION_URL = os.getenv('POSTGRES_URL', 'failed') # 数据库引擎
USER = os.getenv('DATA_BASE_USER', 'failed') # 数据库用户
PASSWORD = os.getenv('DATA_BASE_PWD', 'failed') # 数据库密码
if USER == 'failed' or PASSWORD == 'failed' or CONNECTION_URL == 'failed':
    logger.error(f"数据库用户或密码读取失败, 使用默认配置")
    raise EnvironmentVariableReadException(f"数据库用户或密码读取失败")

CONNECTION_POOL = connection_pool # 连接池大小
BATCH_SIZE = batch_size # 批量大小
PARTITION_NUM = partition_num # 分区数量
ENGINE = engine # 引擎
MAX_WORKERS = max_workers # 最大工作线程数
logger.debug(f"数据库连接参数: CONNECTION_URL, CONNECTION_POOL={CONNECTION_POOL},BATCH_SIZE={BATCH_SIZE},PARTITION_NUM={PARTITION_NUM},ENGINE={ENGINE},MAX_WORKERS={MAX_WORKERS}")