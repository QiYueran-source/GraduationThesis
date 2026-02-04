# 节点

## 1. worker 状态

- 0: 未启动
- 1: 运行中
- 2: 已停止
- -1: 错误

## 2. 命令

以 JSON 发送。

字段：

- **req**
  - 1: 启动命令
  - 0: 状态查询命令
  - -1: 停止命令
- **meta**（仅启动命令携带）

由主机提供，结构如下。约定：**顶层 = 固定**（环境统一），**train_config = 随机**（agent 异质性）。

### 【顶层 = 固定】

- task_id: 任务 id
- start_year: 开始年份
- end_year: 结束年份（end_month 固定为 12，不单独提供接口）
- N: 总股票数量
- stock_list: 股票列表
- factors_list: 因子列表（避免麻烦，直接保存本地）
- earliest_year_month: 最早的年份和月份，(year, month)
- n: 一个组合中的证券数量（算上现金，共 n+1 个证券）
- max_portfolios_num: 对于总共 n 个证券，最多可构建组合数上限
- env_config: 环境配置
  - rf_end_year: 强化学习结束年份（后续年份不再学习但继续计算），月份默认 12
- performance_config: 表现计算配置
  - risk_free_rate: 无风险利率
  - rolling_window: 滚动窗口期数

### 【train_config = 随机】

- seed: 随机种子
- m: 回看的期数
- mask_len: 因子掩码长度，默认 60
- model_config: 模型配置（cate / dropout / config）
- reinforcement_config: 强化学习配置（rl_config / cate / opt: lr, clip_grad_norm, weight_decay）
- reward_config: 奖励配置（reward_weights: rtr / vol / sharpe / max_drawdown）
