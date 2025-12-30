# -*- coding: utf-8 -*-
"""
自定义日志处理器
支持按日期轮转，格式为 app_日期.log
"""
# 库
import os
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml

# 配置和常量  
with open('config/logger.yaml', 'r', encoding = 'utf-8') as f:
    LOGGER_CONFIG = yaml.safe_load(f).get('handlers', {})

# 常量 
FILE_NAMES = LOGGER_CONFIG.get('file_names', 'logs/app')
LEVEL = LOGGER_CONFIG.get('level', 'DEBUG')
WHEN = LOGGER_CONFIG.get('when', 'midnight')
INTERVAL = LOGGER_CONFIG.get('interval', 1)
BACKUP_COUNT = LOGGER_CONFIG.get('backup_count', 5)
ENCODING = LOGGER_CONFIG.get('encoding', 'utf-8')
DELAY = LOGGER_CONFIG.get('delay', False)
UTC = LOGGER_CONFIG.get('utc', False)

class DateRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    自定义日期轮转处理器
    支持 app_日期.log 格式的文件命名
    """
    
    def __init__(self, 
        filename, 
        when='midnight', 
        interval=1, 
        backupCount=5, 
        encoding=None, 
        delay=False, 
        utc=False
    ):
        """
        初始化日期轮转处理器
        
        Args:
            filename: 基础文件名，如 'logs/app.log'
            when: 轮转时机 ('midnight', 'H', 'D' 等)
            interval: 轮转间隔
            backupCount: 保留的文件数量
            encoding: 文件编码
            delay: 是否延迟创建文件
            utc: 是否使用UTC时间
        """
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc)
        self.baseFilename = filename
        self.baseName = os.path.basename(filename)
        self.baseDir = os.path.dirname(filename)
    
    def rotation_filename(self, default_name: str) -> str:
        """
        生成轮转文件名
        将默认的 app.log.2024-01-01 改为 app_2024-01-01.log
        """
        # 获取轮转时间（当前轮转周期的开始时间）
        current_time = datetime.fromtimestamp(self.rolloverAt - 1)
        date_suffix = current_time.strftime('%Y-%m-%d')
        
        # 生成新文件名：app_2024-01-01.log
        base_name = os.path.splitext(self.baseName)[0]  # 移除.log扩展名
        new_name = f"{base_name}_{date_suffix}.log"
        
        return os.path.join(self.baseDir, new_name)


def create_date_rotating_handler() -> DateRotatingFileHandler:
    """
    创建日期轮转处理器
    
    Args:
        filename: 日志文件路径
        level: 日志级别
        when: 轮转时机
        interval: 轮转间隔
        backup_count: 保留文件数
        encoding: 文件编码
        
    Returns:
        DateRotatingFileHandler: 配置好的处理器
    """
    # 确保目录存在
    Path(FILE_NAMES).parent.mkdir(parents=True, exist_ok=True)
    
    # 计算当前日期文件名
    current_date = datetime.now().strftime('%Y-%m-%d')
    base_name = os.path.basename(FILE_NAMES)
    dated_filename = os.path.join(
        os.path.dirname(FILE_NAMES), 
        f"{base_name}_{current_date}.log"
    )
    
    # 创建处理器
    handler = DateRotatingFileHandler(
        filename=dated_filename,  # 使用带日期的文件名
        when=WHEN,
        interval=INTERVAL,
        backupCount=BACKUP_COUNT,
        encoding=ENCODING,
        delay=DELAY,
        utc=UTC
    )
    
    # 设置级别
    level_dict = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    handler.setLevel(level_dict.get(LEVEL.upper(), logging.DEBUG))
    
    return handler