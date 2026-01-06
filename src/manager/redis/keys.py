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

    def __init__(self):
        """简化的Redis前缀管理器
        - 项目根前缀: gt project_prefix     
            - 系统前缀: gt:system system_prefix   
                - 消息队列键: gt:system:Q message_bus_queue_key   
            - 数据前缀: gt:data   
                - 初始化前缀: gt:data:init:  
                    - 初始因子数据键：gt:data:init:factors_df_key  
                    - 初始收益率数据键：gt:data:init:return_df_key    
                - 加载数据前缀: gt:data:load:
                    - 因子数据键：gt:data:load:{{year}}:factors_df_key  
                    - 收益率数据键：gt:data:load:{{year}}:return_df_key  
                - 训练数据前缀: gt:data:train: 
                    - 因子数据键：gt:data:train:{{year}}:{{month}}:{{code}}:factors_df_key  
                    - 收益率数据键：gt:data:train:{{year}}:{{month}}:{{code}}:return_df_key  
        """
        # 定义前缀 
        self._project_prefix = 'gt'
        self._system_prefix = 'system'
        self._data_prefix = 'data'
        self._init_data_prefix = 'init'
        self._load_data_prefix = 'load'
        self._train_data_prefix = 'train'

        # 定义键
        self.message_bus_queue_key = 'Q'
    # ========================================================
    # 前缀
    # ========================================================
    @property
    def project_prefix(self) -> str:
        """获取项目前缀,例如: gt"""
        return self._project_prefix
    
    @property
    def system_prefix(self) -> str:
        """
        例如: gt:system 
        """
        return ":".join([self._project_prefix, self._system_prefix])
    
    @property
    def data_prefix(self) -> str:
        """
        例如: gt:data: 具体数据  
        """
        return ":".join([self._project_prefix, self._data_prefix])
    
    @property
    def init_prefix(self) -> str:
        """
        例如: gt:data:init
        """
        return ":".join([self._data_prefix, self._init_data_prefix])
    
    @property
    def load_prefix(self) -> str:
        """
        例如: gt:data:load
        """
        return ":".join([self._data_prefix, self._load_data_prefix])
    
    @property
    def train_prefix(self) -> str:
        """
        例如: gt:data:train
        """
        return ":".join([self._data_prefix, self._train_data_prefix])

    # ========================================================
    # 构建键
    # ========================================================
    ## 消息队列键
    def build_message_bus_queue_key(self) -> str:
        """
        构建消息队列键
        例如: gt:system:Q
        """
        return ":".join([self.system_prefix, self.message_bus_queue_key])
    
    ##.init键
    def build_init_factors_df_key(self, year: int) -> str:
        """
        构建初始因子数据键
        例如: gt:data:init:{{year}}:factors_df_key
        """
        return ":".join([self.init_prefix, f"{year}", 'factors_df_key'])
    
    def build_init_return_df_key(self, year: int) -> str:
        """
        构建初始收益率数据键
        例如: gt:data:init:{{year}}:return_df_key
        """
        return ":".join([self.init_prefix, f"{year}", 'return_df_key'])
    
