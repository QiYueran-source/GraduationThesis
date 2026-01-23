import src.scripts.set_pypath
import src.manager.database.factors
import datetime as dt

from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR
from src.manager.service import DATA_REDUNDANCY_MONITOR
from src.manager.service import TRAIN_DATA_UPDATER
from src.manager.service import DATA_EXPIRATION_MONITOR
from src.scripts import start_protect, stop_protect

client = REDIS_CONNECTOR.get_client()

# 启动监控
REDIS_MONITOR.start()
# 保护模式关闭
stop_protect()

from src.manager.service import DATABASE_LOADER
from src.manager.service import MESSAGE_BUS, InitMessage, InitMessagePayload


MESSAGE_BUS.publish(
    InitMessage(
        message_type='init', 
        payload = InitMessagePayload(
            
        )
    )
)


import time
#time.sleep(30)
x = DATA_EXPIRATION_MONITOR._get_all_counter()
print(x)

#time.sleep(16)
MESSAGE_BUS.stop()

# 保护模式开启
start_protect()