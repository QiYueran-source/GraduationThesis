"""
日志格式化器
"""

# 库
import logging
import yaml

# 配置和常量  
with open('src/config/logger.yaml', 'r', encoding = 'utf-8') as f:
    LOGGER_CONFIG = yaml.safe_load(f).get('core', {})

# 常量 
DATETIME_FORMAT = LOGGER_CONFIG.get('formatter', {}).get('datetime_format', '%Y-%m-%d %H:%M:%S')

# 自定义格式  
class ModelFormatter(logging.Formatter):
    """
    格式化器
    """
    def __init__(self, prefix: str = 'Logger',dtfmt: str = '%Y-%m-%d %H:%M:%S'):
        """
        初始化格式化器

        Args:
            prefix: 日志前缀
        """
        if prefix:
            fmt = f'%(asctime)s - {prefix} - %(levelname)s - %(message)s'
        else:
            fmt = f'%(asctime)s - %(levelname)s - %(message)s'
        super().__init__(fmt, datefmt=DATETIME_FORMAT)

def create_formatter(prefix: str = 'Logger',dtfmt: str = '%Y-%m-%d %H:%M:%S'):
    """
    创建格式化器
    """
    return ModelFormatter(prefix=prefix, dtfmt=dtfmt)