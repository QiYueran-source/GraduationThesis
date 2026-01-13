from typing import TypedDict, List, Dict, Any, Optional, Literal, Union

# =============================================================================
# Payload类型定义
# =============================================================================
class InitMessagePayload(TypedDict):
    """初始化消息"""
    pass 

class LoadRequestPayload(TypedDict):
    """数据加载请求payload  
    year_list: List[str]  # [2023, 2024]
    stock_pool: str       # "test" | "hs300" | "zz500"
    request_id: int       # 1 
    """
    year_list: List[int]  # [2023, 2024]
    stock_pool: str       # "test" | "hs300" | "zz500"
    request_id: int # 1
    

class DataLoadedPayload(TypedDict):
    """数据加载完成payload
    request_id: str       # "req_001" 自动生成
    data_keys: Dict[str, str]  # {"factors": "gt:data:temp:req_001:factors", "returns": "..."}
    metadata: Dict[str, Any]   # {"stock_count": 1000, "period_count": 12}
    """
    data_keys: Dict[str, str]  # {"factors": "gt:data:temp:req_001:factors", "returns": "..."}
    metadata: Dict[str, Any]   # {"stock_count": 1000, "period_count": 12}

class TrainDataUpdatedPayload(TypedDict):
    """训练数据更新payload"""
    available_periods: int
    cleaned_keys: List[str]     # 被清理的键列表
    new_keys: List[str]         # 新增的键列表

class NodeHealthCheckPayload(TypedDict):
    """节点健康检查payload"""
    node_id: str
    status: str                 # "healthy" | "unhealthy" | "offline"
    metrics: Dict[str, float]   # {"cpu_usage": 45.2, "memory_usage": 67.8}

class ServiceStatusUpdatePayload(TypedDict):
    """服务状态更新payload"""
    service_name: str
    status: str                 # "running" | "stopped" | "error"
    uptime: int                 # 运行时间(秒)
    processed_requests: int     # 已处理请求数

class ShutdownPayload(TypedDict, total=False):
    """关闭信号payload"""
    reason: str                 # "maintenance" | "error" | "manual"
    graceful: bool              # True=优雅关闭, False=强制关闭
    timeout: int                # 关闭超时时间(秒)

# =============================================================================
# 完整的消息类型定义
# =============================================================================

class InitMessage(TypedDict):
    message_type: Literal['init']
    publisher: str
    payload: InitMessagePayload

class LoadRequestMessage(TypedDict):
    """请求加载df"""
    message_type: Literal['load_request']
    publisher: str
    payload: LoadRequestPayload

class DataLoadedMessage(TypedDict):
    message_type: Literal['data_loaded']
    publisher: str
    payload: DataLoadedPayload

class TrainDataUpdatedMessage(TypedDict):
    message_type: Literal['train_data_updated']
    publisher: str
    payload: TrainDataUpdatedPayload

class NodeHealthCheckMessage(TypedDict):
    message_type: Literal['node_health_check']
    publisher: str
    payload: NodeHealthCheckPayload

class ServiceStatusUpdateMessage(TypedDict):
    message_type: Literal['service_status_update']
    publisher: str
    payload: ServiceStatusUpdatePayload

class ShutdownMessage(TypedDict):
    message_type: Literal['shutdown']
    publisher: str
    payload: ShutdownPayload

# =============================================================================
# 联合类型 - 所有消息类型
# =============================================================================

Message = Union[
    InitMessage,
    LoadRequestMessage,
    InitDataLoadedMessage,
    DataLoadedMessage,
    TrainDataUpdatedMessage,
    NodeHealthCheckMessage,
    ServiceStatusUpdateMessage,
    ShutdownMessage
]

MessageType = Literal[
    'init',
    'load_request',
    'init_data_loaded',
    'data_loaded',
    'train_data_updated',
    'node_health_check',
    'service_status_update',
    'shutdown',
    'all'
]