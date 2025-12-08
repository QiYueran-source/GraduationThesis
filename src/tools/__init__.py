"""
agent工具  
- 查询工具
- 交易工具
- 风控工具
- 记忆工具
- 评估工具
- 计算工具
- 决策工具
- 执行工具
- 监控工具
- 报告工具
- 日志工具
"""

from langchain.tools import tool

@tool
def query_data(query: str) -> str:
    """
    查询数据
    """
    return "查询数据"

@tool
def trade(trade: str) -> str:
    """
    交易
    """
    return "交易"

@tool
def risk_control(risk_control: str) -> str:
    """
    风险控制
    """
    return "风险控制"

@tool
def memory(memory: str) -> str:
    """
    """
