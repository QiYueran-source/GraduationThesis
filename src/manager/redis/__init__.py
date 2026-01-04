"""
Redis模块，用于管理Redis连接  
"""
from .connection import RedisConnector
from .exception import RedisException, RedisConnectionException, RedisConfigurationException

# 全局连接管理器