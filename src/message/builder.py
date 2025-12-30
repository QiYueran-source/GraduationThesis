"""
消息构建器   
根据参数，构建消息(prompt)    
"""

# 库
from typing import Dict, Any
from langchain_core.messages import BaseMessage

# 自定义组件
from ..utils import get_module_logger
logger = get_module_logger(__name__,'Message Builder')

class MessageBuilder:
    """
    消息构建器
    """
    
    @staticmethod
    def build_system_message(
        
    ):
        pass 
