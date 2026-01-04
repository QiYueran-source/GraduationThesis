from redis.exceptions import RedisError

class RedisException(RedisError):
    pass

class RedisConnectionException(RedisException):
    pass

class RedisConfigurationException(RedisException):
    pass

class RedisDataException(RedisException):
    pass

class RedisOperationException(RedisException):
    pass