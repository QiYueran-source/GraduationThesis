"""
单轮训练会话：由 run_rounds 以子进程方式调用。
流程：启动总线与 Redis 监控 -> gen_task -> 发布 init -> 等待 shutdown -> 收尾并删除 Redis gt:*
"""
import threading
import time
import uuid
from pathlib import Path

from src.utils.set import set_pypath
set_pypath()

from src.manager.service import MESSAGE_BUS
from src.manager.redis import REDIS_PREFIX_MANAGER, REDIS_CONNECTOR, REDIS_MONITOR
from src.manager.service.message import (
    Message,
    InitMessage,
    InitMessagePayload,
)
from src.utils.set import start_protect, stop_protect
from src.manager.service import (
    NODE_MANAGER,
    DATABASE_LOADER,
    DATA_REDUNDANCY_MONITOR,
    DATA_EXPIRATION_MONITOR,
    TRAIN_DATA_UPDATER,
)
from src.utils.logger import get_module_logger

logger = get_module_logger(__name__, "[RUN_SESSION]")

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "hyparam.yaml"

SHUTDOWN_RECEIVED = threading.Event()


def _shutdown_handler(message: Message):
    logger.info("收到 shutdown 消息，结束等待")
    SHUTDOWN_RECEIVED.set()


def _delete_gt_keys(client, prefix_manager):
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


def gen_task(self_define_prefix: str = "test"):
    if self_define_prefix == "":
        self_define_prefix = "test"
    client = REDIS_CONNECTOR.get_client()
    task_id = time.strftime("%Y%m%d_%H%M") + f"_{self_define_prefix}_{uuid.uuid4()}"
    client.set(name=REDIS_PREFIX_MANAGER.build_task_id_key(), value=task_id)
    result_path = Path(f"./result/{task_id}")
    result_path.mkdir(parents=True, exist_ok=True)


def _startup():
    print("保护模式关闭")
    stop_protect()
    REDIS_MONITOR.start()
    MESSAGE_BUS.start()


def _teardown():
    print("保护模式开启")
    start_protect()
    REDIS_MONITOR.stop()
    if getattr(MESSAGE_BUS, "_running", False):
        MESSAGE_BUS.stop()
    _delete_gt_keys(REDIS_CONNECTOR.get_client(), REDIS_PREFIX_MANAGER)
    print("等待所有工作停止")
    time.sleep(5)


def run_one_session():
    SHUTDOWN_RECEIVED.clear()
    gen_task("baseline")
    init_payload = InitMessagePayload()
    init_message = InitMessage(
        message_type="init",
        publisher="main_thread",
        payload=init_payload,
    )
    MESSAGE_BUS.publish(message=init_message)
    while not SHUTDOWN_RECEIVED.is_set():
        SHUTDOWN_RECEIVED.wait(timeout=1.0)


def main():
    import yaml
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    print("当前配置 (hyparam):")
    print(cfg)

    MESSAGE_BUS.subscribe("shutdown", _shutdown_handler, "RunSession")

    try:
        _startup()
        run_one_session()
    finally:
        _teardown()


if __name__ == "__main__":
    main()
