"""
心理特征枚举 
"""
from enum import Enum

class OptimismLevel(int,Enum):
    OPTIMISTIC = 2
    OBJECTIVE = 1
    PESSIMISTIC = 0

class RationalityLevel(int,Enum):
    RATIONAL = 2
    RANDOM = 1
    EMOTIONAL = 0

class RiskPreferenceLevel(int,Enum):
    HIGH = 2
    MEDIUM = 1
    LOW = 0
