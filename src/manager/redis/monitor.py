"""
redis基础监控  
"""
# 库 
import time
import threading
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from src.manager.redis.connection import RedisConnector

# 日志 
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[RedisMonitor]')

# 异常
from src.manager.redis.exception import (
    RedisException,
    RedisConfigurationException
)

@dataclass
class ConnectionMetrics:
    """连接指标"""
    is_connected: bool = False
    last_check_time: float = 0.0
    connection_latency_ms: float = 0.0
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    reconnect_count: int = 0
    last_reconnect_time: Optional[float] = None
    last_error: Optional[str] = None  # 添加最后一次错误信息
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.successful_checks / self.total_checks if self.total_checks > 0 else 0.0
    
    @property
    def uptime_since_last_reconnect(self) -> float:
        """自上次重连以来的运行时间"""
        if self.last_reconnect_time:
            return time.time() - self.last_reconnect_time
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'is_connected': self.is_connected,
            'last_check_time': self.last_check_time,
            'connection_latency_ms': self.connection_latency_ms,
            'total_checks': self.total_checks,
            'successful_checks': self.successful_checks,
            'failed_checks': self.failed_checks,
            'reconnect_count': self.reconnect_count,
            'last_reconnect_time': self.last_reconnect_time,
            'last_error': self.last_error,
            'success_rate': self.success_rate,
            'uptime_since_reconnect': self.uptime_since_last_reconnect
        }

class ConnectionMonitor:
    """连接监控器"""
    def __init__(self, connector: RedisConnector):
        self.connector = connector
        self.metrics = ConnectionMetrics()
        self._config = {}
        self._lock = threading.Lock()
        self._monitoring = False
        self._logging = False
        self._monitor_thread:Optional[threading.Thread] = None
        self._log_thread:Optional[threading.Thread] = None

        # 加载配置
        self._load_config()

    def _load_config(self):
        """加载配置"""
        try:
            with open('src/config/redis.yaml', 'r', encoding = 'utf-8') as f:
                self._config = yaml.safe_load(f).get('monitoring', {})
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise RedisConfigurationException(f"加载配置失败: {e}")

    def _monitor_loop(self):
        """监控循环 - 更完善的实现，支持快速停止"""
        # 获取配置
        interval = self._config.get('interval', 30)
        max_consecutive_failures = self._config.get('max_consecutive_failures', 5)  # 最大连续失败次数

        # 失败计数
        consecutive_failures = 0

        # 监控循环
        while self._monitoring:
            try:
                # 执行连接检查
                self._check_connection()

                # 根据检查结果处理
                if self.metrics.is_connected:
                    consecutive_failures = 0  # 重置失败计数

                    # 连接正常时的额外处理
                    self._handle_healthy_connection()
                else:
                    consecutive_failures += 1

                    # 连接异常时的处理
                    self._handle_connection_failure(consecutive_failures)

                    # 如果连续失败太多，增加检查间隔（分段sleep）
                    if consecutive_failures >= max_consecutive_failures:
                        extended_interval = interval * 2
                        self._interruptible_sleep(extended_interval)
                        continue

                # 正常检查间隔（分段sleep，便于快速停止）
                self._interruptible_sleep(interval)

            except Exception as e:
                # 监控过程本身的异常
                consecutive_failures += 1
                logger.error(f"监控循环异常: {e}")

                # 防止监控异常导致CPU占用过高
                self._interruptible_sleep(min(interval, 5))

    def _start_monitor_thread(self):
        """启动监控线程"""
        # 获取监控间隔
        interval = self._config.get('interval', 30)

        # 启动监控线程
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon = True,
            name = "RedisMonitor"
        )
        self._monitor_thread.start()

    def _stop_monitor_thread(self):
        """停止监控线程"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
            if self._monitor_thread.is_alive():
                logger.warning("监控线程未能及时停止")
            else:
                logger.info("监控线程已成功停止")

    def _check_connection(self):
        """执行连接状态检查，返回完整的指标对象"""
        with self._lock:
            start_time = time.time()
            
            try:
                # 获取Redis客户端并执行ping检查
                client = self.connector.get_client()
                client.ping()
                
                # 计算延迟
                latency = (time.time() - start_time) * 1000  # 转换为毫秒
                
                # 更新指标
                self.metrics.total_checks += 1
                self.metrics.successful_checks += 1
                self.metrics.last_check_time = time.time()
                self.metrics.connection_latency_ms = latency
                self.metrics.is_connected = True
                
            except Exception as e:
                # 更新失败指标
                self.metrics.total_checks += 1
                self.metrics.failed_checks += 1
                self.metrics.is_connected = False
    
    def _handle_healthy_connection(self):
        """处理连接正常的情况"""
        # 直接使用对象属性
        if self.metrics.connection_latency_ms > 100:
            logger.warning(f"连接延迟较高: {self.metrics.connection_latency_ms:.1f}ms")

    def _handle_connection_failure(self, consecutive_failures: int):
        """处理连接失败的情况"""
        # 获取配置
        max_consecutive_failures = self._config.get('max_consecutive_failures', 5)

        # 可以记录错误到metrics中
        self.metrics.last_error = f"连续失败 {consecutive_failures} 次"
    
        if consecutive_failures == 1:
            logger.error(f"连接检查失败: {self.metrics.last_error}")
        elif consecutive_failures >= max_consecutive_failures:
            logger.error(f"连接连续失败 {consecutive_failures} 次，可能存在严重问题")
    
    def _start_log_thread(self):
        """启动日志记录线程"""
        # 获取配置
        log_interval = self._config.get('metrics_logging_interval', 600)

        # 启动日志记录线程
        self._log_thread = threading.Thread(
            target=self._log_metrics_loop,
            daemon=True,
            name="RedisMonitorLogger"
        )

        # 启动线程
        self._log_thread.start()
        logger.info(f"Metrics日志记录已启动，间隔{log_interval}秒")
    
    def _log_metrics_loop(self):
        """metrics日志记录循环，支持快速停止"""
        # 获取配置
        log_interval = self._config.get('metrics_logging_interval', 600)

        # 日志记录循环 - 检查停止标志
        while self._logging:
            try:
                self._log_current_metrics()
                # 分段sleep，便于快速停止
                self._interruptible_sleep(log_interval)
            except Exception as e:
                logger.error(f"Metrics日志记录异常: {e}")
                # 出错后等待，但也要检查停止标志
                if self._logging:
                    self._interruptible_sleep(10)  # 出错后等待10秒再试
    
    def _log_current_metrics(self):
        """记录当前metrics到日志"""
        with self._lock:
            metrics_dict = self.metrics.to_dict()
        
        # 构建结构化日志消息
        log_message = (
            f"Redis连接状态 - "
            f"连接:{'✓' if metrics_dict['is_connected'] else '✗'}, "
            f"延迟:{metrics_dict['connection_latency_ms']:.1f}ms, "
            f"成功率:{metrics_dict['success_rate']:.1%}, "
            f"检查次数:{metrics_dict['total_checks']}, "
            f"重连次数:{metrics_dict['reconnect_count']}, "
            f"运行时间:{metrics_dict['uptime_since_reconnect']:.0f}秒"
        )
        
        # 根据状态选择日志级别
        if not metrics_dict['is_connected']:
            logger.error(f"[METRICS] {log_message}")
        elif metrics_dict['success_rate'] < 0.95:
            logger.warning(f"[METRICS] {log_message}")
        else:
            logger.info(f"[METRICS] {log_message}")
        
        # 记录详细metrics（debug级别）
        logger.debug(f"[METRICS_DETAIL] {metrics_dict}")
    
    def _interruptible_sleep(self, duration: float):
        """可中断的sleep，便于快速响应停止信号"""
        sleep_step = 1.0  # 每秒检查一次停止标志
        elapsed = 0.0

        while elapsed < duration and (self._monitoring or self._logging):
            remaining = min(sleep_step, duration - elapsed)
            time.sleep(remaining)
            elapsed += remaining

    def _stop_log_thread(self):
        """停止日志记录线程"""
        # 设置停止标志（需要添加self._log_enabled = False）
        self._logging = False

        if self._log_thread and self._log_thread.is_alive():
            self._log_thread.join(timeout=2.0)
            if self._log_thread.is_alive():
                logger.warning("日志记录线程未能及时停止")
            else:
                logger.info("日志记录线程已成功停止")
    
    def start(self):
        """启动监控线程"""
        # 获取配置
        enable_metrics_logging = self._config.get('enable_metrics_logging', True)

        # 检查线程是否已启动
        if self._monitoring:
            # 已经启动 
            logger.warning("监控线程已启动")
        else:
            # 设置监控状态
            self._monitoring = True

            # 获取监控间隔
            interval = self._config.get('interval', 30)
            
            # 启动监控线程
            self._start_monitor_thread()

        # 启动日志记录线程
        if enable_metrics_logging:
            if self._logging:
                # 已经启动 
                logger.warning("日志记录线程已启动")
            else:
                # 设置日志记录状态
                self._logging = True

                # 启动日志记录线程
                self._start_log_thread()
        else:
            logger.info("Metrics日志记录未启用")

    def stop(self) -> bool:
        """停止"""
        # 获取配置
        enable_metrics_logging = self._config.get('enable_metrics_logging', True)

        # 1. 设置停止标志（分离的功能）
        with self._lock:
            self._monitoring = False
            self._logging = False

        # 锁外停止监控线程
        self._stop_monitor_thread()

        # 锁外停止日志记录线程
        if enable_metrics_logging:
            self._stop_log_thread()

        
        # 等待线程结束（锁外等待）
        success = self._wait_for_threads_to_stop()

        # 如果线程都成功停止了，执行清理工作
        if success:
            self._cleanup_after_stop()
            logger.info("Redis连接监控已完全停止")
        else:
            logger.warning("Redis连接监控停止可能不完整")
        
        return success

    def _wait_for_threads_to_stop(self) -> bool:
        """等待线程停止（状态检查版）"""
        # 获取配置
        max_wait_checks = self._config.get('max_wait_checks', 5)
        check_interval = self._config.get('check_interval', 0.5)
        enable_metrics_logging = self._config.get('enable_metrics_logging', True)
        
        logger.debug("开始最终状态检查...")
        
        # 多次检查，确保线程真的停止了
        for check_round in range(max_wait_checks):
            still_alive = []
            
            # 检查监控线程（总是需要检查）
            if self._monitor_thread and self._monitor_thread.is_alive():
                still_alive.append("监控线程")
            
            # 检查日志线程（只有在启用日志功能时才检查）
            if (enable_metrics_logging and 
                self._log_thread and 
                self._log_thread.is_alive()):
                still_alive.append("日志线程")
            elif enable_metrics_logging and self._logging:
                # 日志功能启用但线程对象不存在或已停止
                # 这里可以添加额外检查
                pass
            
            if not still_alive:
                # 所有相关的线程都已停止
                logger.info("所有相关线程已确认停止")
                return True
            
            if check_round == 0:
                # 第一次发现还有线程活着，记录警告
                logger.warning(f"发现未停止的线程: {', '.join(still_alive)}")
            
            # 等待一小段时间后再次检查
            time.sleep(check_interval)
        
        # 经过多次检查后仍有线程未停止
        final_alive = []
        
        # 最终检查监控线程
        if self._monitor_thread and self._monitor_thread.is_alive():
            final_alive.append("监控线程")
        
        # 最终检查日志线程（条件检查）
        if (enable_metrics_logging and 
            self._log_thread and 
            self._log_thread.is_alive()):
            final_alive.append("日志线程")
        
        if final_alive:
            logger.error(f"线程停止失败，最终仍有活跃线程: {', '.join(final_alive)}")
            return False
        
        return True

    def _cleanup_after_stop(self):
        """停止后的清理工作"""
        with self._lock:
            # 重置状态
            self._monitor_thread = None
            self._log_thread = None  
            
            # 记录最后一次检查时间为停止时间
            self.metrics.last_check_time = time.time()

    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            'monitoring_active': self._monitoring,
            'logging': getattr(self, '_logging', False),
            'metrics': self.metrics.to_dict(),
            'config': self._config
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取监控指标"""
        return self.metrics.to_dict()

    def health_check(self) -> bool:
        """快速健康检查"""
        return self.metrics.is_connected and self.metrics.success