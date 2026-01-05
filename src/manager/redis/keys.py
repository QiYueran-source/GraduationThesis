# src/manager/redis/keys.py
"""
Redis键管理和前缀配置
基于YAML配置的简单前缀管理系统
"""

import yaml
from typing import Final, Dict, Optional\

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[RedisKeys]')


class RedisPrefixManager:
    """简化的Redis前缀管理器"""
    
    def __init__(self, config_path: str = "src/config/redis.yaml"):
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, str]:
        """从YAML配置加载前缀"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            prefix_config = config.get('prefix', {})
            
            # 默认配置，如果YAML中没有指定
            defaults = {
                'project': 'default_project',
                'system': 'system',
                'message_bus_queue': 'default_message_bus_queue',
                'data_tag': 'default_data_tag',
            }
            
            # 合并配置
            merged_config = {**defaults, **prefix_config}
            logger.info(f"Redis前缀配置已加载: {merged_config}")
            
            return merged_config
            
        except Exception as e:
            logger.warning(f"无法加载前缀配置，使用默认值: {e}")
            return {
                'project': 'default_project',
                'system': 'system',
                'message_bus_queue': 'default_message_bus_queue',
                'data_tag': 'default_data_tag',
            }
    
    @property
    def project_prefix(self) -> str:
        """获取项目前缀"""
        return self._config['project']
    
    @property
    def system_prefix(self) -> str:
        """
        例如: gt:system 
        """
        return ":".join([self.project_prefix, self._config['system']])
    
    @property
    def data_prefix(self) -> str:
        """
        例如: gt:data: 具体数据  
        """
        return ":".join([self.project_prefix, self._config['data']])
    
    @property
    def message_bus_queue_key(self) -> str:
        """
        例如: gt:system:Q
        """
        return ":".join([self.system_prefix, self._config['message_bus_queue']])
    
    def build_train_data_key(
        self,
        year: int,
        month: int,
        code: str,
    ):
        """
        构建训练数据键
        例如: gt:data: date:code: 具体数据  
        code形如000001
        """
        return ":".join([self.data_prefix, f"{year}{month:02d}", code])

    def get_config(self) -> Dict[str, str]:
        """获取当前配置"""
        return self._config.copy()
    
    def reload_config(self):
        """重新加载配置"""
        self._config = self._load_config()
        logger.info("Redis前缀配置已重新加载")


