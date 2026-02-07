# src/manager/redis/keys.py
"""
Redis键管理和前缀配置
基于YAML配置的简单前缀管理系统
"""

import yaml
from typing import Final, Dict, Optional,Literal

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[RedisKeys]')


class RedisPrefixManager:

    def __init__(self):
        f"""简化的Redis前缀管理器
        - 项目根前缀: gt project_prefix     
            - 系统前缀: gt:system system_prefix   
                - 任务id: gt:system:task_id
                - 消息队列键: gt:system:Q message_bus_queue_key   
                - 节点总信息前缀: gt:system:node_info
            - 数据前缀: gt:data   
                - raw数据框df前缀: gt:data:df:{{year}}
                    - 因子df：gt:data:df:{{year}}:factors_df   
                    - 收益率df：gt:data:df:{{year}}:return_df
                - 训练数据片前缀: gt:data:train:{{year}}:{{month}}:{{code}}   
                - 计数器前缀: gt:data:counter:{{year}}:{{month}}:{{code}} 次数  
        """
        # 定义前缀 
        self._project_prefix = 'gt'
        self._system_prefix = 'system'
        self._node_info_prefix = 'node_info'
        self._task_id_prefix = 'task_id'
        self._data_prefix = 'data'
        self._init_data_prefix = 'init'
        self._load_data_prefix = 'load'
        self._train_data_prefix = 'train'
        self._df_prefix = 'df'
        self._counter_prefix = 'counter'

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
    def train_prefix(self) -> str:
        """
        例如: gt:data:train
        """
        return ":".join([self.data_prefix, self._train_data_prefix])

    @property
    def df_prefix(self) -> str:
        """
        例如: gt:data:df
        """
        return ":".join([self.data_prefix, self._df_prefix])

    @property
    def counter_prefix(self) -> str:
        """
        例如: gt:data:counter
        """
        return ":".join([self.data_prefix, self._counter_prefix])

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

    ## 构建节点总信息键
    def build_node_info_key(self) -> str:
        """
        构建节点总信息键
        例如: gt:system:node_info
        """
        return ":".join([self.system_prefix, self._node_info_prefix])

    ## 构建ID键
    def build_task_id_key(self) -> str:
        """
        构建task_id键  
        例如 gt:system:task_id
        """
        return ":".join([self.system_prefix, self._task_id_prefix])

    ## 构建数据框键
    def build_df_key(self, 
        year: int, 
        key_type:Literal['factors_df','return_df']
    ) -> str:
        """
        构建因子df键
        例如: gt:data:df:2024:factors_df
        """
        return ":".join([self.df_prefix, str(year), key_type])
    
    ## 构建数据片键
    def build_train_slice_key(
        self, 
        year: int, 
        month: int, 
        code: str, 
    ) -> str:
        """
        构建训练数据片键
        
        Args:
            year: 年份
            month: 月份 (1-12)
            code: 证券代码
        
        例如: 
            gt:data:train:2024:01:000001
        
        数据片的形式：列表 [因子(按首字母排序)，收益率]
        """
        month_str = f"{month:02d}"  # 格式化为两位数，如 01, 02
        return ":".join([self.train_prefix, str(year), month_str, code])
    
    ## 构建计数器键
    def build_counter_key(self, year: int, month: int, code: str) -> str:
        """
        构建计数器键
        例如: gt:data:counter:2024:01:000001
        """
        month_str = f"{month:02d}"  # 格式化为两位数，如 01, 02
        return ":".join([self.counter_prefix, str(year), month_str, code])



