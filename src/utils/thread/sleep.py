"""
可中断的等待工具：在长间隔内按小步长睡眠并定期检查“是否继续运行”标志，
便于关闭线程时快速退出，无需等满整个配置间隔。
"""
import time
from typing import Callable


def interruptible_sleep(
    total_seconds: float,
    keep_running: Callable[[], bool],
    check_interval: float = 1.0,
) -> bool:
    """
    可中断的等待：在 total_seconds 内按 check_interval 分段睡眠，每段后检查 keep_running。
    当 keep_running() 返回 False（表示应停止）时立即返回；否则睡满 total_seconds 后返回。

    用于替代 time.sleep(interval)，使工作循环在收到停止信号后能在一个 check_interval 内退出。

    参数
    -----
    total_seconds : float
        计划等待的总时间（秒），对应业务上的间隔，如 config 中的 interval。
    keep_running : Callable[[], bool]
        无参可调用对象，返回 True 表示继续运行、应继续等待，返回 False 表示应停止、立即结束等待。
        例如: lambda: self._monitoring 或 lambda: self.monitor_started。
    check_interval : float, 默认 1.0
        每次睡眠的步长（秒），即检查 keep_running 的频率。不宜过大，否则停止响应仍会变慢。

    返回
    -----
    bool
        True：已睡满 total_seconds（未收到停止信号）。
        False：因 keep_running() 返回 False 而提前结束等待。

    示例
    -----
    >>> # 在监控循环中替代 time.sleep(interval)
    >>> while self._monitoring:
    ...     self._do_work()
    ...     if not interruptible_sleep(600, lambda: self._monitoring, check_interval=1.0):
    ...         break  # 收到停止，退出循环
    """
    if total_seconds <= 0:
        return True
    check_interval = max(0.01, min(check_interval, total_seconds))
    deadline = time.monotonic() + total_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        chunk = min(check_interval, remaining)
        time.sleep(chunk)
        if not keep_running():
            return False
