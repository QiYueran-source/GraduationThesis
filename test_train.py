import src.set_pypath
import src.manager.database.factors
import datetime as dt

from src.manager.redis import RedisConnector
redis_connector = RedisConnector()
client = redis_connector.get_client()

# 存储字符串
client.set("user:name", "张三")
client.set("user:age", 25)

# 存储哈希表 (推荐用于结构化数据)
client.hset("user:1001", "name", "张三")
client.hset("user:1001", "age", 25)
client.hset("user:1001", "email", "zhangsan@example.com")

# 存储JSON数据
import json
user_data = {"name": "张三", "age": 25, "email": "zhangsan@example.com"}
client.set("user:profile", json.dumps(user_data))

redis_connector.close()