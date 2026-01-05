# src/manager/redis/keys.py
"""
Redis键常量定义
统一管理所有Redis键的命名约定
"""

from typing import Final

# =============================================================================
# 命名空间前缀
# =============================================================================
PROJECT_PREFIX: Final[str] = "gt"  # graduation thesis项目前缀

# =============================================================================
# 基础键格式
# =============================================================================

# 节点管理
NODE_COUNT_KEY: Final[str] = f"{PROJECT_PREFIX}:node_num"
NODE_METADATA_KEY_TEMPLATE: Final[str] = f"{PROJECT_PREFIX}:node:{{node_id}}:metadata"

# 数据存储
TRAIN_DATA_KEY_TEMPLATE: Final[str] = f"{PROJECT_PREFIX}:train:{{accper}}:{{stock_code}}"

# 计数器
COUNTER_KEY_TEMPLATE: Final[str] = f"counter:{PROJECT_PREFIX}:factors:{{accper}}:{{stock_code}}"
ACCESS_RECORD_KEY_TEMPLATE: Final[str] = f"access:{{node_id}}:{{accper}}:{{stock_code}}"

# =============================================================================
# 服务管理键格式
# =============================================================================

# 清理管理
CLEANUP_SCHEDULED_KEY_TEMPLATE: Final[str] = f"cleanup:scheduled:{{accper}}:{{stock_code}}"
CLEANUP_INFO_KEY_TEMPLATE: Final[str] = f"cleanup:info:{{accper}}:{{stock_code}}"

# 队列管理
QUEUE_LOAD: Final[str] = "data_manager:load"
QUEUE_UPDATE: Final[str] = "data_manager:update"
QUEUE_CLEANUP: Final[str] = "data_manager:cleanup"

# 队列状态
QUEUE_PROCESSING_SUFFIX: Final[str] = ":processing"
QUEUE_DEAD_LETTER_SUFFIX: Final[str] = ":dead"

# =============================================================================
# 监控和统计键格式
# =============================================================================

# 服务状态
SERVICE_STATUS_KEY: Final[str] = f"{PROJECT_PREFIX}:service:status"
SERVICE_METRICS_KEY: Final[str] = f"{PROJECT_PREFIX}:service:metrics"

# 健康检查
HEALTH_CHECK_KEY: Final[str] = f"{PROJECT_PREFIX}:health:check"
HEALTH_TIMESTAMP_KEY: Final[str] = f"{PROJECT_PREFIX}:health:timestamp"

# =============================================================================
# 键构建函数
# =============================================================================

def build_node_metadata_key(node_id: str) -> str:
    """构建节点元数据键"""
    return NODE_METADATA_KEY_TEMPLATE.format(node_id=node_id)

def build_train_data_key(accper: str, stock_code: str) -> str:
    """构建训练数据键"""
    return TRAIN_DATA_KEY_TEMPLATE.format(accper=accper, stock_code=stock_code)

def build_counter_key(accper: str, stock_code: str) -> str:
    """构建计数器键"""
    return COUNTER_KEY_TEMPLATE.format(accper=accper, stock_code=stock_code)

def build_access_record_key(node_id: str, accper: str, stock_code: str) -> str:
    """构建访问记录键"""
    return ACCESS_RECORD_KEY_TEMPLATE.format(
        node_id=node_id, accper=accper, stock_code=stock_code
    )

def build_cleanup_scheduled_key(accper: str, stock_code: str) -> str:
    """构建清理调度键"""
    return CLEANUP_SCHEDULED_KEY_TEMPLATE.format(accper=accper, stock_code=stock_code)

def build_cleanup_info_key(accper: str, stock_code: str) -> str:
    """构建清理信息键"""
    return CLEANUP_INFO_KEY_TEMPLATE.format(accper=accper, stock_code=stock_code)

def build_queue_processing_key(queue_name: str) -> str:
    """构建队列处理中键"""
    return f"{queue_name}{QUEUE_PROCESSING_SUFFIX}"

def build_queue_dead_letter_key(queue_name: str) -> str:
    """构建死信队列键"""
    return f"{queue_name}{QUEUE_DEAD_LETTER_SUFFIX}"

# =============================================================================
# 键模式匹配
# =============================================================================

# 数据扫描模式
TRAIN_DATA_PATTERN: Final[str] = f"{PROJECT_PREFIX}:train:*:*"
COUNTER_PATTERN: Final[str] = f"counter:{PROJECT_PREFIX}:factors:*:*"
CLEANUP_SCHEDULED_PATTERN: Final[str] = "cleanup:scheduled:*:*"
ACCESS_RECORD_PATTERN_TEMPLATE: Final[str] = "access:{{node_id}}:*:*"

def get_train_data_pattern_for_stock(stock_code: str) -> str:
    """获取指定证券的训练数据模式"""
    return f"{PROJECT_PREFIX}:train:*:{stock_code}"

def get_counter_pattern_for_stock(stock_code: str) -> str:
    """获取指定证券的计数器模式"""
    return f"counter:{PROJECT_PREFIX}:factors:*:{stock_code}"

def get_access_record_pattern_for_node(node_id: str) -> str:
    """获取指定节点的访问记录模式"""
    return ACCESS_RECORD_PATTERN_TEMPLATE.format(node_id=node_id)

# =============================================================================
# 键过期时间
# =============================================================================

# 默认过期时间（秒）
DEFAULT_ACCESS_RECORD_TTL: Final[int] = 86400  # 24小时
DEFAULT_CLEANUP_COUNTDOWN: Final[int] = 300    # 5分钟
DEFAULT_HEALTH_CHECK_TTL: Final[int] = 60      # 1分钟

# =============================================================================
# 键验证函数
# =============================================================================

def validate_key_format(key: str, expected_template: str) -> bool:
    """验证键格式是否符合模板"""
    import re
    
    # 将模板转换为正则表达式
    pattern = re.escape(expected_template)
    pattern = pattern.replace(r"\{.*?\}", ".*")
    
    return bool(re.match(f"^{pattern}$", key))

def parse_train_data_key(key: str) -> tuple[str, str]:
    """解析训练数据键，返回(accper, stock_code)"""
    if not validate_key_format(key, TRAIN_DATA_KEY_TEMPLATE):
        raise ValueError(f"无效的训练数据键格式: {key}")
    
    parts = key.split(":")
    if len(parts) >= 4:
        return parts[2], parts[3]
    raise ValueError(f"无法解析训练数据键: {key}")

def parse_counter_key(key: str) -> tuple[str, str]:
    """解析计数器键，返回(accper, stock_code)"""
    if not validate_key_format(key, COUNTER_KEY_TEMPLATE):
        raise ValueError(f"无效的计数器键格式: {key}")
    
    parts = key.split(":")
    if len(parts) >= 5:
        return parts[3], parts[4]
    raise ValueError(f"无法解析计数器键: {key}")