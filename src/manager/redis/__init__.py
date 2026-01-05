"""
Redis模块，用于管理Redis连接  
"""
from .connection import RedisConnector
from .monitor import ConnectionMonitor
from .exception import RedisException, RedisConnectionException, RedisConfigurationException

# 全局连接管理器
REDIS_CONNECTOR = RedisConnector() 
REDIS_MONITOR = ConnectionMonitor(REDIS_CONNECTOR)

__all__ = [
    'RedisConnector',
    'ConnectionMonitor',
    'RedisException',
    'RedisConnectionException',
    'RedisConfigurationException',
    'REDIS_CONNECTOR',
    'REDIS_MONITOR'
]