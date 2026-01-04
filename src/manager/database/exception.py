class DatabaseException(Exception):
    '''数据库异常总类'''  

class ConfigReadException(DatabaseException):
    '''配置读取异常'''  

class EnvironmentVariableReadException(DatabaseException):
    '''环境变量读取异常'''

class DatabaseReadException(DatabaseException):
    '''数据库读取异常'''  

class PerfromCalculateException(DatabaseException):
    '''表现计算异常'''  