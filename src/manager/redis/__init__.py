"""
Redis模块，用于管理Redis连接  
"""
from src.manager.redis.connection import RedisConnector
from src.manager.redis.monitor import ConnectionMonitor
from src.manager.redis.exception import RedisException, RedisConnectionException, RedisConfigurationException
from src.manager.redis.keys import RedisPrefixManager

# 全局连接管理器
REDIS_CONNECTOR = RedisConnector() 
REDIS_MONITOR = ConnectionMonitor(REDIS_CONNECTOR)
REDIS_PREFIX_MANAGER = RedisPrefixManager()

__all__ = [
    'RedisConnector',
    'ConnectionMonitor',
    'RedisException',
    'RedisConnectionException',
    'RedisConfigurationException',
    'REDIS_CONNECTOR',
    'REDIS_MONITOR',
    'REDIS_PREFIX_MANAGER'
]