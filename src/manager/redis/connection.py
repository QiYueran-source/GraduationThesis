"""
Redis连接管理
"""
# 库
import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
import yaml
import dotenv
import os 
import time 

# 加载环境变量
dotenv.load_dotenv()

# 异常
from src.manager.redis.exception import (
    RedisException,
    RedisConnectionException,
    RedisConfigurationException
)

# 日志  
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[RedisConnection]')


# redis连接管理  
class RedisConnector:
    def __init__(self):
        self._client = None
        self._is_connected = False
        self._last_health_check = 0  
        self._config = {}
    
    def _load_config(self):
        password = os.getenv('REDIS_PWD', 'failed')
        if password == 'failed':
            logger.error(f"Redis密码读取失败")
            raise RedisConfigurationException(f"Redis密码读取失败")

        try:
            with open('src/config/redis.yaml', 'r', encoding = 'utf-8') as f:
                self._config = yaml.safe_load(f)
                self._config = {
                    **self._config, 'password': password
                }

        except Exception as e:
            logger.error(f"Redis配置读取失败: {e}")
            raise RedisConfigurationException(f"Redis配置读取失败: {e}")
    
    def _create_client(self):
        param = self._config.get('parameters', {})
        is_retry = self._config.get('retry',{}).get('retry_on_timeout', False)

        if is_retry:
            retry_param = self._config.get('retry',{})
            retry_delay = retry_param.get('retry_delay', 1)
            retry_cap_multiplier = retry_param.get('cap_multiplier', 10)
            retry_max_retries = retry_param.get('max_retries', 3)
            retry_config = Retry(
                backoff=ExponentialBackoff(
                    cap=retry_delay * retry_cap_multiplier,
                    base=retry_delay
                ),
                retries=retry_max_retries
            )

            param = {
                **param,
                'retry': retry_config
            }
        
        try:
            self._client = redis.Redis(**param)
            logger.debug(f"Redis连接创建成功: {self._client}")
        except Exception as e:
            logger.error(f"Redis连接创建失败: {e}")
            raise RedisConnectionException(f"Redis连接创建失败: {e}")

    def _health_check(self) -> bool:
        """检查Redis连接是否健康"""
        try:
            if self._client:
                self._client.ping()
                self._last_health_check = time.time()
                self._is_connected = True
                logger.debug(f"Redis连接健康检查成功")
                return True
        except Exception as e:
            logger.warning(f"Redis健康检查失败: {e}")
            self._is_connected = False
            return False
        return False
    
    def _reconnect(self) -> None:
        """重新连接Redis"""
        logger.info("开始重新连接Redis...")
        try:
            # 清理旧连接
            if self._client:
                self._client.close()
            
            # 重新创建连接
            self._create_client()
            logger.info("Redis重连成功")
            
        except Exception as e:
            logger.error(f"Redis重连失败: {e}")
            raise RedisConnectionException(f"重连失败: {e}")
    
    def get_client(self) -> redis.Redis:
        """获取Redis客户端 (核心接口)"""
        # 检查连接状态
        if self._client is None or not self._is_connected:
            self._load_config()  # 确保配置已加载
            self._create_client()  # 创建连接
            return self._client
        
        # 定期健康检查
        current_time = time.time()
        health_check_interval = self._config.get('monitoring', {}).get('health_check_interval', 30)
        if current_time - self._last_health_check > health_check_interval:
            if not self._health_check():
                logger.warning("Redis健康检查失败，尝试重连...")
                self._reconnect()
        return self._client

    def close(self) -> None:
        """关闭Redis连接"""
        if self._client:
            self._client.close()
            self._client = None
            self._is_connected = False
            logger.info("Redis连接已关闭")
        else:
            logger.warning("Redis连接已关闭")