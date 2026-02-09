"""
启动程序  
"""
# 库
import uuid  
import time
import threading
from pathlib import Path
import sys

# 设置路径
from src.utils.set import set_pypath
set_pypath()

# 启动消息总线
from src.manager.service import MESSAGE_BUS
MESSAGE_BUS.start()  # 启动消息总线

# 组件
from src.manager.redis import REDIS_PREFIX_MANAGER, REDIS_CONNECTOR, REDIS_MONITOR
from src.manager.service.message import (
    Message,
    InitMessage, InitMessagePayload,
    ShutdownPayload, ShutdownMessage,
    ClearPortPayload, ClearPortMessage,
    WaitingPayload, WaitingMessage,
)
from src.utils.set import start_protect, stop_protect
from src.manager.service import (
    # 引入以初始化  
    NODE_MANAGER,
    DATABASE_LOADER,
    DATA_REDUNDANCY_MONITOR,
    DATA_EXPIRATION_MONITOR,
    TRAIN_DATA_UPDATER
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, "[START]")

# 收到 shutdown 后置位，main 中 wait 直到此事件
SHUTDOWN_RECEIVED = threading.Event()


def _shutdown_handler(message: Message):
    """收到 shutdown 消息时置位，使 main 中的 wait 返回。"""
    logger.info("收到 shutdown 消息，结束等待")
    SHUTDOWN_RECEIVED.set()


def _delete_gt_keys(client, prefix_manager):
    """退出前删除本项目占用的 Redis 键（前缀 gt）。"""
    prefix = prefix_manager.project_prefix
    pattern = f"{prefix}*"
    deleted = 0
    try:
        for key in client.scan_iter(match=pattern):
            client.delete(key)
            deleted += 1
        if deleted:
            logger.info(f"退出前已删除 {deleted} 个 Redis 键（pattern={pattern}）")
    except Exception as e:
        logger.warning(f"删除 gt 键时异常: {e}")


MESSAGE_BUS.subscribe('shutdown', _shutdown_handler, 'StartScript')

# 构建任务ID  
def gen_task(self_define_prefix:str = "test"):
    if self_define_prefix == "":
        self_define_prefix = "test"

    # 创建键
    client = REDIS_CONNECTOR.get_client()
    task_id = time.strftime("%Y%m%d_%H%M") + f"_{self_define_prefix}_{uuid.uuid4()}"
    client.set(
        name = REDIS_PREFIX_MANAGER.build_task_id_key(),
        value = task_id
    )

    # 创建结果路径
    result_path = Path(f"./result/{task_id}")
    result_path.mkdir(parents=True, exist_ok=True)

    
def main():
    """启动主函数"""  
    # redis客户端 
    client = REDIS_CONNECTOR.get_client()

    # 启动redis线程
    REDIS_MONITOR.start()

    # 保护模式关闭
    print("保护模式关闭")
    stop_protect()

    # 是否清理
    clear_port = input("是否清理端口池(y/n): ")
    if clear_port == "y":
        clear_port_payload = ClearPortPayload()
        clear_port_message = ClearPortMessage(
            message_type='clearport',
            publisher='NodeManager',
            payload=clear_port_payload
        )
        MESSAGE_BUS.publish(message=clear_port_message)

    # 生成任务ID
    self_define_prefix = input("请输入任务前缀(默认为test): ")
    gen_task(self_define_prefix)


    # 发布初始化消息 
    while True:
        start_now = input('start?[y/n]: ')
        if start_now == "y":
            init_payload = InitMessagePayload()
            init_message = InitMessage(
                message_type='init',
                publisher='main_thread',
                payload=init_payload
            )
            MESSAGE_BUS.publish(message=init_message)
            break
        else:
            time.sleep(1)
            continue

    # 等待 shutdown 消息（短超时循环，便于响应 Ctrl+C）
    logger.info("等待 shutdown 消息…")
    while not SHUTDOWN_RECEIVED.is_set():
        SHUTDOWN_RECEIVED.wait(timeout=1.0)
    logger.info("shutdown 已收到，main 退出")

    


if __name__ == "__main__":
    try:
        exit_code = 0
        logger.info("===========启动程序===========")
        main()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
        client = REDIS_CONNECTOR.get_client()
        raw = client.get(REDIS_PREFIX_MANAGER.build_task_id_key())
        task_id = raw.decode('utf-8') if isinstance(raw, bytes) else (raw or '')
        if task_id is not None and task_id:
            MESSAGE_BUS.publish(
                message = WaitingMessage(
                    message_type='waiting',
                    publisher='main_thread',
                    payload=WaitingPayload(
                        task_id=task_id, 
                        reason='keyboard_interrupt'
                    )
                )
            )
        SHUTDOWN_RECEIVED.wait(timeout = 300)
        logger.info("===========收到中断信号===========")
        exit_code = 0
    except Exception as e:
        logger.error(f"启动程序失败: {e}")
        exit_code = 1
    finally:
        logger.info("===========程序结束===========")
        print("保护模式开启")
        start_protect() # 保护模式开启
        REDIS_MONITOR.stop()
        MESSAGE_BUS.stop()
        _delete_gt_keys(REDIS_CONNECTOR.get_client(), REDIS_PREFIX_MANAGER)
        print("等待所有工作停止")
        time.sleep(5) # 等待所有工作停止
        sys.exit(exit_code)