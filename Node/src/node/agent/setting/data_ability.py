"""
数据能力枚举  

分析能力：输出的长度，设定为
"""
from enum import Enum

class AnalysisAbility(int,Enum):
    SHORT = 300 # 300 tokens 
    MEDIUM = 600 # 600 tokens 
    LONG = 900 # 900 tokens 

class ReviewAbility(int,Enum):
    pass