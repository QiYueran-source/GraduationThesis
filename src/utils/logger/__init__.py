
# -*- coding: utf-8 -*-
"""
日志管理模块
"""
# 库 
import logging
import yaml

# 自定义组件
from .handler import create_date_rotating_handler
from .formatter import create_formatter

# 配置和常量  
with open('src/config/logger.yaml', 'r', encoding = 'utf-8') as f:
    LOGGER_CONFIG = yaml.safe_load(f).get('logger', {})

# 常量 
LEVEL = LOGGER_CONFIG.get('level', 'DEBUG')
DEFAULT_PREFIX = LOGGER_CONFIG.get('default_prefix', '[Logger]')  

# 创建logger
def get_module_logger(module_name: str, prefix: str = DEFAULT_PREFIX):
    """
    获取模块日志器
    """
    handler = create_date_rotating_handler()
    formatter = create_formatter(prefix=prefix)

    # 设置格式化器到处理器
    handler.setFormatter(formatter)

    # 创建logger
    logger = logging.getLogger(module_name)
    logger.setLevel(LEVEL)
    logger.addHandler(handler)
    return logger

# 导出 
__all__ = ['get_module_logger']
