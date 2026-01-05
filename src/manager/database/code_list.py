"""
证券列表加载
"""
from typing import Literal

def get_code_list(
    code_type:Literal['test'],
    quanlity_threshold:float = None 
):
    if code_type == 'test':
        return ['000001']
    else:
        raise NotImplementedError 