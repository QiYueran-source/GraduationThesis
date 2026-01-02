"""
Agent模块，用于构建Agent相关的类和函数  
1.数据获取，启动任务后，可以从redis中获取数据   
2.net层:使用net中的网络，输入因子，输出动作    
3.reward层:计算奖励，根据实际收益和预测收益的差异，计算奖励，使用SB3进行强化学习  

稳健性：  
使用net预测收益和方差，使用scipy优化器得到最优动作，取代直接使用net输出动作    
使用反向传播，而不是强化学习更新参数    
"""  

import torch


class TradingAgent:
    def __init__(self,
        
    ):
       pass 