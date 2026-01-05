import src.set_pypath
import src.manager.database.factors
import datetime as dt

from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR

client = REDIS_CONNECTOR.get_client()

# 启动监控
REDIS_MONITOR.start()

from src.manager.service import DATABASE_LOADER
from src.manager.service import MESSAGE_BUS, InitMessage
print(MESSAGE_BUS.subscribers)
MESSAGE_BUS.start()
MESSAGE_BUS.publish(
    InitMessage(
        type='init', 
        payload={'year_list': ['2023', '2024'], 'stock_pool': 'test'}
        )
    )
MESSAGE_BUS.publish(
    InitMessage(
        type='init', 
        payload={'year_list': ['2023', '2024'], 'stock_pool': 'test'}
        )
    )


MESSAGE_BUS.stop()