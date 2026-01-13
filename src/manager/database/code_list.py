"""
证券列表加载
"""
from typing import Literal

def get_code_list(
    code_type:Literal['test'],
    quanlity_threshold:float = None 
):
    if code_type == 'test':
        return ['000001','000002','000003','000004','000005','000006','000007','000008','000009','000010']
    else:
        raise NotImplementedError 