"""
消息总线  
"""
# 库
import redis 
import threading
from typing import Callable, List, Dict, Any
import json
import time
import yaml
import functools

# 组件
from src.manager.redis import REDIS_CONNECTOR,RedisConnector, REDIS_PREFIX_MANAGER
from .message import Message, MessageType

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[MessageBus]')

# 异常
from .exception import ServiceConfigurationException

# 消息总线
class MessageBus:
    def __init__(self):
        self.connector = REDIS_CONNECTOR
        self.client = self.connector.get_client()

        self.system_queue_tag = REDIS_PREFIX_MANAGER.message_bus_queue_key
        self.subscribers = {}
        self._running = False
        self._subscriber_thread = None
        self._message_count_lock = threading.Lock() # 消息计数器锁  
        self._message_count = 0  # 消息计数器
        self._req_id_count_lock = threading.Lock() # req_id计数器锁  
        self._req_id_count = 0  # req_id计数器
        self._config = {}

        self._load_config()
        self.ttl = self.config.get('ttl', 3600)
        self.timeout = self.config.get('timeout', 5)


    def _load_config(self):
        # 加载配置
        try:
            with open('src/config/redis.yaml', 'r', encoding = 'utf-8') as f:
                self.config = yaml.safe_load(f).get('message_bus', {})
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise ServiceConfigurationException(f"加载配置失败: {e}")

    def subscribe(self, message_type: MessageType, handler: Callable, module_name:str = 'unknown'):
        """订阅消息处理器
        
        Args:
            message_type: 消息类型
            handler: 消息处理函数，签名: handler(message: dict) -> None
        """
        if message_type not in self.subscribers:
            self.subscribers[message_type] = []
        self.subscribers[message_type].append(handler)
        logger.debug(f"已订阅消息类型: {module_name}:{message_type} -> {handler.__name__}")

    def _dispatch_message(self, message: dict):
        """分发消息给订阅者"""
        import concurrent.futures
        message_type = message.get('message_type')

        # 分发给特定类型的订阅者
        if message_type in self.subscribers:
            for handler in self.subscribers[message_type]:
                try:
                    thread = threading.Thread(
                        target=handler, 
                        args=(message,),
                        daemon=True  # 设为守护线程，随主程序退出
                    )
                    thread.start()
                except Exception as e:
                    logger.error(f"消息处理器异常: {e}")

            logger.debug(f"消息 {message_type} 已分发给 {len(self.subscribers[message_type])} 个处理器")

        # 分发给订阅所有消息的处理器
        if 'all' in self.subscribers:
            for handler in self.subscribers['all']:
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        executor.submit(handler, message)
                except Exception as e:
                    logger.error(f"全订阅消息处理器异常: {e}")
    
    def _start_subscriber_thread(self):
        """启动订阅者线程"""
        def subscriber_loop():
            """订阅者主循环"""
            logger.info("消息订阅者线程启动")
            
            while self._running:
                try:
                    # 监听系统消息队列
                    system_queue = self.system_queue_tag
                    result = self.client.brpop([system_queue], timeout=self.timeout)
                    
                    if result:
                        queue_name, message_json = result
                        
                        try:
                            # 解析消息
                            message = json.loads(message_json)

                            # 分发消息
                            self._dispatch_message(message)
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"消息解析失败: {e}, 原始消息: {message_json}")
                        except Exception as e:
                            logger.error(f"消息处理异常: {e}")
                            
                except Exception as e:
                    logger.error(f"订阅者循环异常: {e}")
                    time.sleep(1)  # 避免频繁重试
        
        # 创建并启动线程
        self._subscriber_thread = threading.Thread(
            target=subscriber_loop,
            name="MessageBusSubscriber", 
            daemon=True
        )
        self._subscriber_thread.start()
        logger.info("消息订阅者线程已启动")

    def start(self):
        """启动消息总线"""
        self._running = True
        self._start_subscriber_thread()
        logger.info("消息总线已启动")

    def _stop_subscriber_thread(self):
        """停止订阅者线程"""
        if self._subscriber_thread and self._subscriber_thread.is_alive():
            self._subscriber_thread.join(timeout=self.timeout)
            if self._subscriber_thread.is_alive():
                logger.warning(f"订阅者线程未能在{self.timeout}秒内停止")
        logger.info("订阅者线程已停止")

    def stop(self):
        """停止消息总线"""
        self._running = False
        self._stop_subscriber_thread()
        logger.info("消息总线已停止")

    def publish(self, message: Message) -> str:
        """发布消息到队列，自动生成ID"""
        try:
            # 自动生成ID和时间戳
            with self._message_count_lock:
                self._message_count += 1
                msg_type = message.get('message_type', 'unknown')
                message['id'] = f"{msg_type}_{self._message_count:06d}"
                message['timestamp'] = time.time()
                
            # 序列化并发布
            message_json = json.dumps(message)
            system_queue = self.system_queue_tag

            # 使用LPUSH保证FIFO顺序
            self.client.lpush(system_queue, message_json)

            # 设置过期时间，避免队列积压
            self.client.expire(system_queue, self.ttl)

            logger.debug(f"消息已发布: {message.get('message_type')}, ID: {message['id']}, Timestamp: {message['timestamp']}")
            return message['id'], message['timestamp']

        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            raise

# 全局消息总线 
MESSAGE_BUS = MessageBus()

# 使用示例
"""
MessageBus的订阅方法：

## 推荐方式：在__init__中注册处理器
class DatabaseLoader:
    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus

        # 注册消息处理器
        self.bus.subscribe('load_request')(self.handle_load_request)
        self.bus.subscribe('shutdown')(self.handle_shutdown)

    def handle_load_request(self, message: dict):
        '''处理数据加载请求'''
        logger.info(f"加载请求: {message['id']}")
        self.load_data(message)

    def handle_shutdown(self, message: dict):
        '''处理关闭信号'''
        logger.info(f"关闭信号: {message['id']}")
        self.cleanup()

## 统一消息处理器的另一种方式
class UnifiedHandler:
    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus

        # 订阅所有消息，然后在处理器内部判断类型
        self.bus.subscribe()(self.handle_all_messages)

    def handle_all_messages(self, message: dict):
        '''处理所有类型的消息'''
        msg_type = message['type']

        if msg_type == 'load_request':
            self._handle_load(message)
        elif msg_type == 'data_loaded':
            self._handle_data_loaded(message)
        elif msg_type == 'shutdown':
            self._handle_shutdown(message)
"""



