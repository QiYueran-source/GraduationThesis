"""
启动程序  
"""
# 库
import uuid  
import time

# 组件
from src.manager.redis import REDIS_PREFIX_MANAGER, REDIS_CONNECTOR

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, "[START]")

# 构建任务ID  
def gen_task():
    client = REDIS_CONNECTOR.get_client()
    task_id = time.strftime("%Y%m%d_%H%M") + f"_{uuid.uuid4()}"
    client.set(
        name = REDIS_PREFIX_MANAGER.build_task_id_key(),
        value = task_id
    )


    


