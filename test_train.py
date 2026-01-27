import src.utils.set.set_pypath
import src.manager.database.factors
import datetime as dt

from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR
from src.manager.service import DATA_REDUNDANCY_MONITOR
from src.manager.service import TRAIN_DATA_UPDATER
from src.manager.service import DATABASE_LOADER
from src.manager.service import DATA_EXPIRATION_MONITOR
from src.utils.set import start_protect, stop_protect
from src.manager.service import MESSAGE_BUS, InitMessage, InitMessagePayload


# 启动监控
REDIS_MONITOR.start()
MESSAGE_BUS.start()

# 保护模式关闭
stop_protect()

# 打印因子
from src.manager.database import get_factors_info

MESSAGE_BUS.publish(
    InitMessage(
        message_type='init', 
        payload = InitMessagePayload(
            
        )
    )
)


import time
time.sleep(3)


time.sleep(1600)
MESSAGE_BUS.stop()

# 保护模式开启
start_protect()