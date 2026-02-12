class ServiceException(Exception):
    '''服务异常总类'''  


class ServiceConfigurationException(ServiceException):
    '''服务配置异常'''  

class ServiceInitException(ServiceException):
    '''服务初始化异常'''  

class DataExpException(ServiceException):
    '''数据过期异常'''