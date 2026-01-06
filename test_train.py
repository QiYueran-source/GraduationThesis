import src.set_pypath
import src.manager.database.factors
import datetime as dt

from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR

client = REDIS_CONNECTOR.get_client()

# 启动监控
REDIS_MONITOR.start()

from src.manager.service import DATABASE_LOADER
from src.manager.service import MESSAGE_BUS, InitMessage, InitMessagePayload

MESSAGE_BUS.start()
MESSAGE_BUS.publish(
    InitMessage(
        type='init', 
        payload = InitMessagePayload(
            
        )
    )
)

import time
time.sleep(10)
MESSAGE_BUS.stop()