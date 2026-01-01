# LangChain  
## 1.llm工作脚手架  
- plan 意图  
- action 行动  
- tool 工具  
- memory 记忆  
- streaming 流式处理  
- structured output 标准化输出  

还有一些中间件：middleware  
- 日志 
- 中断  

高级功能  
- 上下文  
- 人机交互  
- 多Agent  

## 数据库交互与Agent健壮性  
SQL-Agent  
    - 分析用户查询意图  
    - 生成sql语句 
    - 使用查询工具  
返回Tool Message  

SQL查询可能有错误，如字段错误，表名错误  
    - 如果错误，需要解析错的message  

## react 框架  
- 推理  
- 行动  
- 观察  

request->model->tools-->model(check)-->result  
                    |____| 
其中，虚线是动态边，需要


## langchain与langgraph 
langchain用于简单的智能体    
langgraph用于更加复杂的流程  

## 系统提示 PROMPT  
prompt提示是重要的约束，约束智能体的权限和行为  
