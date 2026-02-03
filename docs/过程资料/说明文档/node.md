# 节点

## 1.worker状态  
 

## 2.命令  
以json来启动  

字段:  
- 1.req 
    - 1:启动命令   
    - 0:状态查询命令  
    - -1：停止命令  
- 2.meta: (仅启动命令带相关内容)  
    - task_id: 任务id    
    - start_year: 开始年份  
    - end_year: 停止年份 
    - end_month: 停止月份
    - N: 总股票数量    
    - stock_list: 股票列表   
    - factors_list: 因子列表（避免麻烦，直接保存本地）   
    - earliest_year_month: 最早的年份和月份,(year, month)  
    - train_config: 训练配置   
        - seed: 种子
        - n: 一个组合中的证券数量（算上现金，共n+1个证券）  
        - max_portfolios_num: 对于总共n个证券，最多可以构建C(N,n)个组合,太大，所以设置最大组合数量    
        - m: 回看的期数      
        - mask_len: 因子掩码长度 
        - model_config: 模型配置 
            - cate: 0表示mlp1, 
            - config: 模型具体参数
        - performance_config: # 表现计算配置  
            - risk_free_rate: 无风险利率   
            - rolling_window: 滚动窗口期数  
        - reward_config: 奖励配置   
            - reward_weights: 奖励权重
                - rtr: 收益率权重   
                - vol: 波动权重   
                - sharpe: 夏普比率权重   
                - max_drawdown: 最大回测权重    