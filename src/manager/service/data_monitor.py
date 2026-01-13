"""
redis数据监控器  
1.数据是否充足 redun_monitor  
2.数据是否过期 exp_monitor  
"""
# 库
import threading
from typing import Any,Optional
import time
import yaml

# 组件
from src.manager.redis import REDIS_CONNECTOR
from src.manager.redis import REDIS_PREFIX_MANAGER
from .bus import MESSAGE_BUS 
from .message import (
    Message,
    InitMessage,InitMessagePayload,
    LoadRequestMessage,LoadRequestPayload
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__,'[DataMonitor]')

# 异常 
from .exception import * 

# 数据冗余监控器 
class DataRedundancyMonitor:
    def __init__(self):
        # redis客户端
        self.client = REDIS_CONNECTOR.get_client()

        # 内部变量
        self.started = False # 启动标志
        self.now_year = 0 # 当前年份
        self.loader_year = [] # 已加载年份
        self.waiting_for_update = False # 等待数据更新  
        self.req_count = 0 # 请求记录

        # 配置
        self._train_param = {}
        self._redundancy_param = {}

        # 加载配置 
        self._load_config() 
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()  # 保护共享状

        # 线程管理 


        # 初始化now_year
        self.now_year = self._train_param.get('start_year',1997)

        # 注册
        self._subscribe()

    def _load_config(self):
        # 加载配置
        try:
            with open('src/config/hyparam.yaml', 'r', encoding = 'utf-8') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise ServiceConfigurationException(f"加载配置失败: {e}")
        
        # 分离配置  
        self._train_param = config.get('train',{})
        self._redundancy_param = config.get('redis_redundancy',{}) 

        if not self._train_param or not self._redundancy_param:
            logger.error('data_monitor配置加载异常')
            raise 
        
        # 检查配置逻辑 
        if self._redundancy_param.get('min_periods_year',1)>=self._redundancy_param.get('max_periods_year',2):
            logger.error(f"最小年份冗余({self._redundancy_param.get('min_periods_year',1)})应该大于最大年份冗余({self._redundancy_param.get('max_periods_year',1)})")
            raise 

    def start(self):
        """启动监控器循环"""
        with self._lock:
            if self.started:
                logger.warning('数据冗余监控器已经启动')
                return
            
            # 设置启动标志
            self.started = True
            
            # 启动监控线程
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="DataRedundancyMonitor",
                daemon=True  # 设为守护线程，随主程序退出
            )
            self._monitor_thread.start()
            logger.info('数据冗余监控器已启动')

    def _count_slice_year(self) -> int:
        """监控redis中有多少年的数据片
        
        Returns:
            int: 数据片的年份数量
        """
        # 构建扫描模式：gt:data:train:*
        pattern = f"{REDIS_PREFIX_MANAGER.train_prefix}:*"
        
        # 使用集合存储不重复的年份
        years = set()
        cursor = 0
        
        try:
            # 使用 SCAN 命令遍历所有匹配的键（避免阻塞）
            while True:
                cursor, keys = self.client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=1000  # 每次扫描1000个键
                )
                
                # 从键中提取年份
                # 键格式：gt:data:train:2024:01:000001:factors
                #         或 gt:data:train:2024:01:000001:return
                for key in keys:
                    parts = key.split(':')
                    # 确保键格式正确，至少有年份部分（第4个部分，索引3）
                    if len(parts) >= 4:
                        try:
                            year = int(parts[3])  # 提取年份
                            years.add(year)
                        except (ValueError, IndexError):
                            # 如果年份部分不是数字，跳过
                            logger.debug(f"无法解析年份，键: {key}")
                            continue
                
                # 如果 cursor 为 0，表示扫描完成
                if cursor == 0:
                    break
            
            year_count = len(years)
            logger.debug(f"扫描完成，发现 {year_count} 年的数据片: {sorted(years)}")
            return year_count
            
        except Exception as e:
            logger.error(f"统计数据片年份失败: {e}")
            raise

    def _monitor_loop(self):
        """
        开启监控循环  
        - 检测当前的年份  
        - 如果 已有年份<=min，则加载 max-已有年份 的数据进入（发布加载事件）  
        - 年份前进 max-已有年份  
        - 如果年份>最大年份，则发布结束事件  
        - 发布加载事件后，设置等待=True,直到监听到更新成功事件后，才继续监控
        """
        count = 0 # 记录监控次数  

        while self.started:
            loaded_year_count = self._count_slice_year()

            # 如果数据充足，则停止
            if loaded_year_count > self._redundancy_param.get('min_periods_year',1):
                count+=1
                logger.info(f'第{count}次检测，没有缺失，等待{self._redundancy_param.get('interval',120)}s')
                time.sleep(self._redundancy_param.get('interval',120))
                continue

            # 如果不足，发布加载事件(次数为)
            load_years = self._redundancy_param.get('max_periods_year',2) - loaded_year_count
            self.req_count+=1 # req计数器+1
            payload = LoadRequestPayload(
                year_list=[self.now_year + i for i in range(1,load_years+1)],
                stock_pool = self._train_param.get('stock_pool','test'),
                request_id = self.req_count
            )
            load_message = LoadRequestMessage(
                message_type='load_request',
                publisher=self.__class__.__name__,
                payload=payload
            )
            MESSAGE_BUS.publish(
                message = load_message
            )
            logger.info(f'发布数据加载事件，加载年份:{payload["year_list"]}')

            # 发布后，进入循环等待，直到更新事件完成
            self.waiting_for_update = True
            wait_interval = 5
            while self.waiting_for_update:
                time.sleep(wait_interval)

    def stop(self, timeout: float = 10.0) -> bool:
        """停止监控器
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        with self._lock:
            if not self.started:
                logger.warning('数据冗余监控器未启动')
                return True
            
            # 设置停止标志
            self.started = False
            self.waiting_for_update = False  # 取消等待状态
        
        # 等待监控线程结束
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.info(f'等待监控线程结束（超时: {timeout}秒）...')
            self._monitor_thread.join(timeout=timeout)
            
            if self._monitor_thread.is_alive():
                logger.warning(f'监控线程未能在{timeout}秒内停止')
                return False
            else:
                logger.info('监控线程已成功停止')
        
        # 清理线程引用
        with self._lock:
            self._monitor_thread = None
        
        logger.info('数据冗余监控器已完全停止')
        return True

    def data_loaded_handler(self,message:Message):
        """注册更新事件
        - 解除waiting状态  
        """
        if message.get('payload',{}).get('request_id',0) == self.req_count:
            self.waiting_for_update = False
        elif message.get('payload',{}).get('request_id',0) < self.req_count:
            logger.info(f'目前有{self.req_count}个请求，完成到第{message.get('payload',{}).get('request_id',0)}，继续等待')
        else:
            logger.error('加载数量超过请求，异常')
            raise  
    
    def init_handler(self,message:Message):
        """注册初始化事件  
        - 启动冗余监控器  
        """
        self.start()

    def shutdown_handler(self,message:Message):
        """注册结束处理器  
        - 关闭线程  
        """
        self.stop()

    def _subscribe(self):
        MESSAGE_BUS.subscribe('init',self.init_handler,'DataRedundancyMonitor')
        MESSAGE_BUS.subscribe('data_loaded',self.data_loaded_handler,'DataRedundancyMonitor')
        MESSAGE_BUS.subscribe('shutdown',self.shutdown_handler,'DataRedundancyMonitor')

DATA_REDUNDANCY_MONITOR = DataRedundancyMonitor()


        