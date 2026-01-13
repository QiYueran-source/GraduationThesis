"""
更新器  
1.有新的df加载后，转换为数据片，加载到redis
    - 数据标准化  
    - 数据补全  
2.保证redis中只有max_period期df，用于数据补全
"""
# 库
import polars as pl
import redis 
import yaml
import pickle
from threading import Lock

# 组件
from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR, REDIS_PREFIX_MANAGER
from src.manager.service.bus import MESSAGE_BUS
from src.manager.service.message import (
    Message,
    DataLoadedMessage,DataLoadedPayload
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[TrainDataUpdater]')

# 训练数据更新器  
class TrainDataUpdater:

    def __init__(self):
        # redis客户端
        self.client = REDIS_CONNECTOR.get_client()

        # 内部变量
        self.latest_df:pl.DataFrame = None # 最新的数据框，用于填充
        self.now_year:int = 0 # 当前年份

        # 线程锁，保证一次只处理一个年份的数据
        self.lock = Lock()

        # 注册处理器
        self._subscribe()

    def data_loaded_handler(self, message: Message):
        """处理数据加载事件
        - 1.加载df  
        - 2.因子标准化  
        - 3.连接因子和收益率（收益率的日期滞后一月）    
        - 4.纵向合并df，进行填充  
        - 5.将数据处理为数据片  
        注意，一次处理一年的数据,需要加锁   
        """
        with self.lock:
            # 1.加载df  
            year = message['payload']['year']
            factors_df = pickle.loads(self.client.get(REDIS_PREFIX_MANAGER.build_df_key(year,'factors_df')))
            return_df = pickle.loads(self.client.get(REDIS_PREFIX_MANAGER.build_df_key(year,'return_df')))
            self.now_year = year

            # 2.因子标准化  
            std_factors_df = factors_df.group_by('stkcd').agg(
                [
                    pl.col(factor).std().alias(factor)
                    for factor in factors_df.columns if factor != 'stkcd' or factor != 'accper'
                ]
            )

            # 3.连接因子和收益率（收益率的日期滞后一月）    
            return_df = return_df.with_columns(
                pl.col('accper').dt.offset_by('-1mo').alias('accper')
            )
            merged_df:pl.DataFrame = std_factors_df.join(return_df, on=['stkcd','accper'], how='left') # TODO 这一步大概率有问题  

            # 4.纵向合并df，进行填充（如果latest_df不存在，则使用向前-向后-补0三步骤填充）
            if self.latest_df is None:
                clean_df = merged_df.fill_null(strategy='forward').fill_null(strategy='backward').fill_null(value=0)
            else:
                clean_df = merged_df.vstack(self.latest_df).fill_null(strategy='forward').filter(pl.col('accper').dt.year() == self.now_year)
            self.latest_df = clean_df

            # 5.将数据处理为数据片  
            for row in clean_df.to_dicts():
                code = row.pop('stkcd')
                accper = row.pop('accper')
                year,month = accper.year(),accper.month()
                monthly_return = row.pop('monthly_return')
                sorted_factors = list(sorted(row.items(), key=lambda x: x[0]).values()) # 按首字母排序
            
                # 构建数据片键
                train_slice_key = REDIS_PREFIX_MANAGER.build_train_slice_key(year,month,code)
                self.client.set(
                    name = train_slice_key,
                    value = pickle.dumps([sorted_factors,monthly_return]),
                    ex=7200
                )
            

    def _subscribe(self):
        MESSAGE_BUS.subscribe(
            message_type='data_loaded',
            handler=self.data_loaded_handler
        )

TRAIN_DATA_UPDATER = TrainDataUpdater()