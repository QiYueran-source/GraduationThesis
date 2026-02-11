"""
redis数据监控器  
1.数据是否充足 redun_monitor  
2.数据是否过期 exp_monitor  
"""
# 库
import polars as pl
import threading
from typing import Any,Optional
import time
import yaml
from typing import Dict
from collections import defaultdict

# 组件
from src.manager.redis import REDIS_CONNECTOR
from src.manager.redis import REDIS_PREFIX_MANAGER
from src.manager.service.bus import MESSAGE_BUS 
from src.manager.service.message import (
    Message,
    StartMessage,StartMessagePayload,
    LoadRequestMessage,LoadRequestPayload,
    WaitingMessage,WaitingPayload
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__,'[DataMonitor]')

# 异常 
from src.manager.service.exception import *
from src.utils.thread import interruptible_sleep 

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
        self._stock_pool_param = {}
        self._meta_param = {}
        self._redundancy_param = {}

        # 加载配置 
        self._load_config() 

        # 线程管理 
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()  # 保护共享状态

        # 初始化now_year（meta.start_year 的前一年，表示当前 redis 中最大数据片年份的前一年）
        self.now_year = self._meta_param.get('start_year', 1997) - 1

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
        
        # 分离配置（弃用 train，改用 stock_pool + meta）
        self._stock_pool_param = config.get('stock_pool', {})
        self._meta_param = config.get('meta', {})
        self._redundancy_param = config.get('redis_redundancy', {})

        if not self._meta_param or not self._redundancy_param:
            logger.error('data_monitor配置加载异常：需提供 meta 与 redis_redundancy')
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
        - 如果年份>=最大年份，则退出监控循环（等待由任务启动时统一发 waiting）
        - 发布加载事件后，设置等待=True,直到监听到更新成功事件后，才继续监控
        """
        count = 0 # 记录监控次数  
        end_year = self._meta_param.get('end_year', 2025)

        while self.started:
            # 检查是否到达 end_year（仅退出循环，不再发布 waiting，由任务启动时统一发 waiting）
            with self._lock:
                if self.now_year >= end_year:
                    logger.info(f'到达结束年份 end_year={end_year}, now_year={self.now_year}，退出监控循环')
                    break

            loaded_year_count = self._count_slice_year()

            # 如果数据充足，则静默等待（仅缺失数据时记录日志）；可中断便于停止时快速退出
            if loaded_year_count > self._redundancy_param.get('min_periods_year',1):
                count += 1
                if not interruptible_sleep(
                    self._redundancy_param.get('interval', 120),
                    lambda: self.started,
                    check_interval=1.0,
                ):
                    break
                continue

            # 如果不足，发布加载事件(次数为)
            load_years = self._redundancy_param.get('max_periods_year',2) - loaded_year_count
            self.req_count+=1 # req计数器+1
            year_list = [self.now_year + i for i in range(1, load_years+1) if self.now_year + i <= end_year]
            
            # 如果 year_list 为空且 now_year >= end_year，退出监控循环
            if not year_list and self.now_year >= end_year:
                logger.info(f'year_list 为空且 now_year={self.now_year} >= end_year={end_year}，退出监控循环')
                break
            
            payload = LoadRequestPayload(
                year_list=year_list,
                stock_pool=self._stock_pool_param.get('pool_type', 'test'),
                request_id=self.req_count
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
            timeout = 3600
            start_wait_time = time.time()
            while self.waiting_for_update and self.started:
                # 检查是否超时 
                if time.time() - start_wait_time > timeout:
                    logger.error(f"等待数据更新超时（{timeout}秒），req_id: {self.req_count}")
                    self.waiting_for_update = False
                    break
                # 等待（可中断，便于停止时快速退出）
                if not interruptible_sleep(wait_interval, lambda: self.started, check_interval=1.0):
                    break

    def _publish_waiting(self):
        """发布 waiting 事件（由 NodeManager 处理等待逻辑）"""
        # 从 Redis 获取当前 task_id
        try:
            task_id_key = REDIS_PREFIX_MANAGER.build_task_id_key()
            task_id = self.client.get(task_id_key)
            if not task_id:
                logger.error(f'无法从 Redis 获取 task_id (键: {task_id_key})')
                task_id = 'unknown'
        except Exception as e:
            logger.error(f'获取 task_id 失败: {e}')
            task_id = 'unknown'
        
        end_year = self._meta_param.get('end_year', 2025)
        
        # 构建并发布 WaitingMessage
        payload = WaitingPayload(
            task_id=task_id,
            reason='reached_end_year',
            end_year=end_year,
            current_year=self.now_year
        )
        waiting_message = WaitingMessage(
            message_type='waiting',
            publisher=self.__class__.__name__,
            payload=payload
        )
        
        MESSAGE_BUS.publish(message=waiting_message)
        logger.info(f'发布 waiting 事件: task_id={task_id}, reason=reached_end_year, end_year={end_year}, current_year={self.now_year}')

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
        - 更新 now_year
        """
        with self._lock:  # 🔒 加锁保护共享状态
                request_id = message.get('payload', {}).get('request_id', 0)
                year = message.get('payload', {}).get('year', 0)  # 获取加载的年份
                
                if request_id == self.req_count:
                    # ✅ 更新 now_year（确保不倒退）
                    if year > self.now_year:
                        self.now_year = year
                        logger.info(f'now_year 更新为: {self.now_year}')
                    
                    # ✅ 更新等待状态
                    self.waiting_for_update = False
                    logger.info(f'收到匹配的更新消息，req_id: {request_id}，year: {year}')
                    
                elif request_id < self.req_count:
                    logger.debug(f'收到较早的更新消息，req_id: {request_id}，当前等待: {self.req_count}，继续等待')
                else:
                    logger.error(f'收到未来的更新消息，req_id: {request_id}，当前等待: {self.req_count}，异常')
                    raise 
    
    def start_handler(self,message:Message):
        """注册启动事件  
        - 启动冗余监控器  
        """
        self.start()

    def shutdown_handler(self,message:Message):
        """注册结束处理器  
        - 关闭线程  
        """
        self.stop()

    def _subscribe(self):
        MESSAGE_BUS.subscribe('start',self.start_handler,'DataRedundancyMonitor')
        MESSAGE_BUS.subscribe('data_loaded',self.data_loaded_handler,'DataRedundancyMonitor')
        MESSAGE_BUS.subscribe('shutdown',self.shutdown_handler,'DataRedundancyMonitor')

DATA_REDUNDANCY_MONITOR = DataRedundancyMonitor()


class DataExpirationMonitor:
    def __init__(self):
        """数据过期监控器
        1.获取node_info中的node_num  
        2.获取
        """
        # redis客户端
        self.client = REDIS_CONNECTOR.get_client()

        # 配置
        self._expiration_param = {}

        # 线程管理
        self.started = False # 启动标志
        self._lock = threading.Lock()

        # 加载配置
        self._load_config()

        # 注册
        self._subscribe()

    def _load_config(self):
        """加载配置"""
        try:
            with open('src/config/hyparam.yaml', 'r', encoding = 'utf-8') as f:
                config = yaml.safe_load(f)
                self._expiration_param = config.get('redis_expiration', {})
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise 

    def _get_node_num(self) -> int:
        """获取node_info中的node_num"""
        node_info = self.client.hgetall(REDIS_PREFIX_MANAGER.build_node_info_key())
        node_num = int(node_info.get('node_num', 0))
        logger.info(f"获取node_num: {node_num}")
        return max(node_num, 1)

    def _get_all_counter(self)->pl.DataFrame:
        """获取所有数据计数器
        - year: 年份
        - month: 月份
        - code: 股票代码
        - count: 计数  
        如果没有计数器，返回空df  
        """
        counter_pattern = f"{REDIS_PREFIX_MANAGER.counter_prefix}:*"  

        result_list = [] 
        cursor = 0
        while True:
            # 调用 scan：cursor 是上一次返回的游标，初始为0
            cursor, keys = self.client.scan(cursor=cursor, match=counter_pattern, count=5000)
            
            # 处理本次返回的键（即使 keys 为空，也不提前 break）
            if keys:  # 只有有键时才处理，避免空循环
                values = self.client.mget(keys)
                # 你的解析逻辑...（不变）
                for key, value in zip(keys, values):
                    if value is None:
                        continue
                    key_parts = key.split(":")
                    if len(key_parts) < 6:
                        print(f"无效的 Redis 键格式：{key}，跳过")
                        continue
                    year = int(key_parts[-3])
                    month = int(key_parts[-2])
                    code = key_parts[-1]
                    count = int(value)
    
                    result_list.append(
                        pl.DataFrame({
                            'year': [year],
                            'month': [month],
                            'code': [code],
                            'count': [count]
                        })
                    )
    
            # 核心终止条件：cursor=0 表示遍历完毕
            if cursor == 0:
                break  # 只有游标回到0，才终止循环
        
        if result_list:            
            return pl.concat(result_list)
        else:
            return pl.DataFrame()

    def _expiration_loop(self):
        """数据过期循环
        1.遍历所有数据计数器，如果计数器的计数大于等于node_num * clean_up_threshold，则启动倒计时，倒计时结束后，删除数据
        2.如果计数==node_num，则删除数据
        3.检测和清理孤岛数据（不与当前加载年份连续的过期年份）
        """
        while self.started:
            counter_df = self._get_all_counter()  # 获取所有数据计数器

            if counter_df.is_empty():
                if not interruptible_sleep(
                    self._expiration_param.get('interval', 30),
                    lambda: self.started,
                    check_interval=1.0,
                ):
                    break
                continue  

            # 1.判断哪些已经被全部访问 
            all_visited_df = counter_df.filter(pl.col('count') == self._get_node_num())

            # 初始化删除用的 Pipeline
            delete_pipeline = self.client.pipeline(transaction=False)  # 非事务模式，更快
            if not all_visited_df.is_empty():
                # 批量收集删除命令（无需循环执行，一次性添加到 Pipeline）
                for row in all_visited_df.to_dicts():
                    year, month, code = row['year'], row['month'], row['code']
                    # 添加删除 train_slice 键的命令
                    delete_pipeline.delete(REDIS_PREFIX_MANAGER.build_train_slice_key(year, month, code))
                    # 添加删除 counter 键的命令
                    delete_pipeline.delete(REDIS_PREFIX_MANAGER.build_counter_key(year, month, code))
                # 一次性执行所有删除命令（核心优化！）
                delete_pipeline.execute()

            # 从df中移除这些数据
            counter_df = counter_df.join(all_visited_df, on=['year','month','code'], how='anti')

            # 2.检测和清理孤岛数据（不与当前加载年份连续的过期年份）
            isolated_years = self._detect_isolated_years()
            if isolated_years:
                self._cleanup_isolated_years(isolated_years)

            # 从df中移除孤岛年份的数据
            if isolated_years and not counter_df.is_empty():
                isolated_years_df = pl.DataFrame({'year': list(isolated_years)})
                counter_df = counter_df.join(isolated_years_df, on='year', how='anti')

            # 3.判断哪些需要启动倒计时
            clean_up_threshold = self._expiration_param.get('clean_up_threshold', 0.85)
            clean_up_countdown = self._expiration_param.get('clean_up_countdown', 300)
            need_countdown_df = counter_df.filter(pl.col('count') >= self._get_node_num() * clean_up_threshold)

            # 初始化设置用的 Pipeline
            set_pipeline = self.client.pipeline(transaction=False)
            if not need_countdown_df.is_empty():
                # 批量收集 set 命令
                for row in need_countdown_df.to_dicts():
                    year, month, code = row['year'], row['month'], row['code']
                    # 添加设置 counter 键的命令
                    set_pipeline.set(
                        REDIS_PREFIX_MANAGER.build_counter_key(year, month, code),
                        clean_up_countdown
                    )
                # 一次性执行所有 set 命令
                set_pipeline.execute()

            # 循环休眠，避免空转占用CPU（可中断，便于停止时快速退出）
            if not interruptible_sleep(
                self._expiration_param.get('interval', 30),
                lambda: self.started,
                check_interval=1.0,
            ):
                break

    def _detect_isolated_years(self) -> set[int]:
        """检测孤岛年份：不与当前加载年份连续的过期年份

        逻辑：
        1. 获取当前所有数据年份（通过train数据键）
        2. 从最大年份开始向前检查连续性
        3. 找到第一个断开点，返回断开点及之前的所有年份作为孤岛数据
        """
        try:
            # 获取当前存在的所有年份
            years = self._get_all_data_years()
            if not years:
                return set()

            # 排序年份
            sorted_years = sorted(years)
            logger.debug(f"当前数据年份: {sorted_years}")

            if len(sorted_years) <= 1:
                return set()

            # 从最大年份开始向前检查连续性
            max_year = sorted_years[-1]
            isolated_years = set()

            # 检查连续段
            current_streak = [max_year]

            for i in range(len(sorted_years) - 2, -1, -1):  # 从倒数第二个开始向前
                current_year = sorted_years[i]
                expected_next = current_streak[-1] - 1

                if current_year == expected_next:
                    # 连续，继续添加
                    current_streak.append(current_year)
                else:
                    # 断开了，前面的所有年份都标记为孤岛数据
                    break

            # 如果有连续段，则断开点之前的所有年份都作为孤岛数据
            if len(current_streak) < len(sorted_years):
                # 找到断开点
                break_point = current_streak[-1] - 1
                isolated_years = set(year for year in sorted_years if year <= break_point)

                if isolated_years:
                    logger.info(f"检测到时间断开点 {break_point}，发现 {len(isolated_years)} 个孤岛年份: {sorted(isolated_years)}")

            return isolated_years

        except Exception as e:
            logger.error(f"检测孤岛年份失败: {e}")
            return set()

    def _get_all_data_years(self) -> set[int]:
        """获取当前Redis中存在的所有数据年份（通过train数据键）"""
        pattern = f"{REDIS_PREFIX_MANAGER.train_prefix}:*"
        years = set()
        cursor = 0

        try:
            while True:
                cursor, keys = self.client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=1000
                )

                for key in keys:
                    parts = key.split(':')
                    if len(parts) >= 4:
                        try:
                            year = int(parts[3])
                            years.add(year)
                        except (ValueError, IndexError):
                            continue

                if cursor == 0:
                    break

            return years

        except Exception as e:
            logger.error(f"获取数据年份失败: {e}")
            return set()

    def _cleanup_isolated_years(self, isolated_years: set[int]):
        """清理孤岛年份的所有数据"""
        if not isolated_years:
            return

        # 获取清理时间配置
        isolated_data_exp = self._expiration_param.get('isolated_data_exp', 60)

        cleanup_pipeline = self.client.pipeline(transaction=False)
        cleanup_count = 0

        try:
            # 清理每个孤岛年份的数据
            for year in isolated_years:
                # 查找该年份的所有计数器
                counter_pattern = f"{REDIS_PREFIX_MANAGER.counter_prefix}:{year}:*"
                cursor = 0

                while True:
                    cursor, keys = self.client.scan(
                        cursor=cursor,
                        match=counter_pattern,
                        count=1000
                    )

                    for counter_key in keys:
                        # 从计数器键提取年月代码
                        parts = counter_key.split(':')
                        if len(parts) >= 6:
                            try:
                                year_val = int(parts[-3])
                                month_val = int(parts[-2])
                                code_val = parts[-1]

                                # 构建对应的数据片键
                                slice_key = REDIS_PREFIX_MANAGER.build_train_slice_key(year_val, month_val, code_val)

                                # 添加到清理队列
                                cleanup_pipeline.expire(counter_key, isolated_data_exp)
                                cleanup_pipeline.expire(slice_key, isolated_data_exp)
                                cleanup_count += 1

                            except (ValueError, IndexError):
                                continue

                    if cursor == 0:
                        break

            # 执行清理
            if cleanup_count > 0:
                cleanup_pipeline.execute()
                logger.info(f"已设置 {cleanup_count} 个孤岛数据 {isolated_data_exp} 秒后清理")

        except Exception as e:
            logger.error(f"清理孤岛年份失败: {e}")  

    def start(self):
        with self._lock:
            if self.started:
                logger.warning('数据过期监控器已经启动')
                return
        
            # 设置启动标志
            self.started = True
            
            # 创建线程（在锁内，因为很快）
            self._monitor_thread = threading.Thread(
                target=self._expiration_loop,
                name="DataExpirationMonitor",
                daemon=True
            )
    
        # 锁外启动线程（避免线程启动时访问锁）
        self._monitor_thread.start()
        logger.info('数据过期监控器已启动')            


    def stop(self, timeout: float = 10.0) -> bool:
        """停止数据过期监控器
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        try:
            # 锁内：检查和修改共享状态
            with self._lock:
                if not self.started:
                    logger.warning('数据过期监控器未启动')
                    return True
                
                # 设置停止标志
                self.started = False
                
                # 获取线程引用（在锁内）
                monitor_thread = self._monitor_thread
            
            # 锁外：等待线程结束
            if monitor_thread and monitor_thread.is_alive():
                logger.info(f'等待监控线程结束（超时: {timeout}秒）...')
                monitor_thread.join(timeout=timeout)
                
                if monitor_thread.is_alive():
                    logger.warning(f'监控线程未能在{timeout}秒内停止')
                    return False
                else:
                    logger.info('监控线程已成功停止')
            
            # 锁内：清理线程引用
            with self._lock:
                self._monitor_thread = None
            
            logger.info('数据过期监控器已完全停止')
            return True
            
        except Exception as e:
            logger.error(f"停止数据过期监控器时发生异常: {e}", exc_info=True)
            # 即使出错，也尝试清理状态
            with self._lock:
                self.started = False
                self._monitor_thread = None
            return False

    def first_train_data_update_handler(self,message:Message):
        """第一次加载后，启动"""
        if message['payload']['first']:
            self.start()

    def shutdown_handler(self, message:Message):
        self.stop()
    
    def _subscribe(self):
        """订阅数据加载事件"""
        MESSAGE_BUS.subscribe('train_data_updated',self.first_train_data_update_handler,'DataExpirationMonitor')
        MESSAGE_BUS.subscribe('shutdown',self.shutdown_handler,'DataExpirationMonitor')

DATA_EXPIRATION_MONITOR = DataExpirationMonitor()