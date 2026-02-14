from typing import TypedDict, List, Dict, Any, Optional, Literal, Union

# =============================================================================
# Payload类型定义
# =============================================================================
class InitMessagePayload(TypedDict):
    """初始化消息"""
    pass 

class StartMessagePayload(TypedDict):
    """启动消息"""
    pass 

class LoadRequestPayload(TypedDict):
    """数据加载请求 payload；证券列表由 database_loader 通过 get_code_list() 从 Redis meta 获取"""
    year_list: List[int]  # [2023, 2024]
    request_id: int
    

class DataLoadedPayload(TypedDict):
    """数据加载完成payload
    request_id: int       # 1 相应loadrequest的id
    year:int             # 2024 一次只提供一个年份
    """
    request_id: int       # 1 相应loadrequest的id
    year:int             # 2024 

class TrainDataUpdatedPayload(TypedDict):
    """训练数据更新payload"""
    first:bool                  # 是否是第一次发布 


class WaitingPayload(TypedDict):
    """等待节点完成payload"""
    task_id: str                # 当前任务ID
    reason: str                 # 等待原因（如 "reached_end_year"）
    end_year: int               # 结束年份
    current_year: int           # 当前年份

class ShutdownPayload(TypedDict, total=False):
    """关闭信号payload"""
    reason: str                 # "maintenance" | "error" | "manual"
    graceful: bool              # True=优雅关闭, False=强制关闭
    timeout: int                # 关闭超时时间(秒)


class ClearPortPayload(TypedDict):
    """清空端口池 payload，无额外字段"""
    pass


# =============================================================================
# 完整的消息类型定义
# =============================================================================

class InitMessage(TypedDict):
    message_type: Literal['init']
    publisher: str
    payload: InitMessagePayload

class StartMessage(TypedDict):
    message_type: Literal['start']
    publisher: str
    payload: StartMessagePayload

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

class WaitingMessage(TypedDict):
    message_type: Literal['waiting']
    publisher: str
    payload: WaitingPayload

class ShutdownMessage(TypedDict):
    message_type: Literal['shutdown']
    publisher: str
    payload: ShutdownPayload


class ClearPortMessage(TypedDict):
    message_type: Literal['clearport']
    publisher: str
    payload: ClearPortPayload


# =============================================================================
# 联合类型 - 所有消息类型
# =============================================================================

Message = Union[
    InitMessage,
    LoadRequestMessage,
    DataLoadedMessage,
    TrainDataUpdatedMessage,
    StartMessage,
    WaitingMessage,
    ShutdownMessage,
    ClearPortMessage
]

MessageType = Literal[
    'init',
    'load_request',
    'init_data_loaded',
    'data_loaded',
    'train_data_updated',
    'start',
    'waiting',
    'shutdown',
    'clearport',
    'all'
]