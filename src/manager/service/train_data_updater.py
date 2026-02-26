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
import json
from threading import Lock
import time

# 组件
from src.manager.database import get_factors_info
from src.manager.redis import REDIS_CONNECTOR, REDIS_MONITOR, REDIS_PREFIX_MANAGER
from src.manager.service.bus import MESSAGE_BUS
from src.manager.service.message import (
    Message,
    DataLoadedMessage,DataLoadedPayload,
    TrainDataUpdatedMessage,TrainDataUpdatedPayload
)
from src.manager.service.exception import DataExpException

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, prefix='[TrainDataUpdater]')

# 训练数据更新器  
class TrainDataUpdater:

    def __init__(self):
        # redis客户端
        self.client = REDIS_CONNECTOR.get_client()

        # 内部变量
        self.first = True
        self.latest_df:pl.DataFrame = None # 最新的数据框，用于填充
        self.now_year:int = 0 # 当前年份
        self.factors = sorted([s.lower() for s in get_factors_info()['factor_name'].to_list()])

        # 线程锁，保证一次只处理一个年份的数据
        self.lock = Lock()

        # 配置
        self._updater_retry_config = {}
        self._risk_free_rate = 0.00

        # 加载配置
        self._load_config()

        # 注册处理器
        self._subscribe()

    def _load_config(self):
        """加载配置"""
        try:
            with open('src/config/hyparam.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._updater_retry_config = config.get('updater_retry', {})
                self._risk_free_rate = float(config.get('meta',{}).get('performance_config',{}).get('risk_free_rate', 0.00))
        except Exception as e:
            logger.error(f"加载updater_retry配置失败: {e}")
            # 默认配置
            self._updater_retry_config = {'max_retries': 5, 'retry_delay': 1.0}
            self._risk_free_rate = 0.00

    # 数据片加载
    def _load_data_from_redis(self, year: int) -> tuple[pl.DataFrame, pl.DataFrame]:
        """从Redis加载因子和收益率数据，支持重试机制解决时序竞争"""
        # 获取重试配置
        max_retries = self._updater_retry_config.get('max_retries', 5)
        retry_delay = self._updater_retry_config.get('retry_delay', 1.0)

        # 1. 构建Redis键
        factors_key = REDIS_PREFIX_MANAGER.build_df_key(year, 'factors_df')
        return_key = REDIS_PREFIX_MANAGER.build_df_key(year, 'return_df')

        # 2. 重试机制：解决时序竞争问题
        for attempt in range(max_retries):
            # 查看是否被删除
            is_deleted = self.client.get(REDIS_PREFIX_MANAGER.build_deleted_df_year_key(year))
            if is_deleted:
                logger.info(f'{year}年份数据已过期，不再加载')
                raise DataExpException(f'{year} df数据已经过期')

            # 读取并校验数据
            factors_raw = self.client.get(factors_key)
            return_raw = self.client.get(return_key)

            if factors_raw and return_raw:
                # 数据存在，继续正常处理
                break

            # 数据不存在，重试
            if attempt < max_retries - 1:
                logger.warning(f"年份{year}的因子/收益率数据暂不存在，重试 {attempt + 1}/{max_retries}，等待 {retry_delay}s")
                time.sleep(retry_delay)
            else:
                logger.error(f"年份{year}的因子/收益率数据在重试{max_retries}次后仍不存在")
                raise Exception 

        # 3. 解析JSON并转为DataFrame（增加异常处理）
        try:
            factors_df_dicts = json.loads(factors_raw)
            return_df_dicts = json.loads(return_raw)
        except json.JSONDecodeError as e:
            raise Exception(f"年份{year}的JSON数据解析失败: {e}") from e
        
        # 4. 定义schema并转为Polars DF + 日期转换（容错+指定时区）
        # factors schema
        factors_schema = {
            'stkcd': pl.Utf8,
            'accper': pl.Utf8,
        }
        factors_schema.update({factor: pl.Float64 for factor in self.factors})

        # return schema
        return_schema = {
            'stkcd': pl.Utf8,
            'accper': pl.Utf8,
            'monthly_return': pl.Float64
        }

        date_parse_expr = pl.col('accper').str.strptime(
            pl.Date, format='%Y-%m-%d', strict=False  # strict=False跳过非法日期
        ).fill_null(pl.date(1900,1,1))  # 非法日期转为1900-01-01，后续过滤

        factors_df = pl.DataFrame(factors_df_dicts, schema=factors_schema).with_columns(date_parse_expr)
        return_df = pl.DataFrame(return_df_dicts, schema=return_schema).with_columns(date_parse_expr)

        # 5. 数据类型校验（因子列转为数值型，避免字符串导致后续计算失败）
        # 填充空值和NaN为0.0
        # 只对因子列进行精确填充
        factors_df = factors_df.with_columns([
            pl.col(f).cast(pl.Float64, strict=False)
                    .fill_null(0.0)
                    .fill_nan(0.0)
                    .alias(f)
            for f in self.factors
        ])

        return_df = return_df.with_columns(
            pl.col('monthly_return').cast(pl.Float64, strict=False)
                                    .fill_null(0.0)
                                    .fill_nan(0.0)
        )

        # 6. 过滤非法数据
        factors_df = factors_df.filter(pl.col('accper') != pl.date(1900,1,1))
        return_df = return_df.filter(pl.col('accper') != pl.date(1900,1,1))

        return factors_df, return_df

    def _standardize_factors(self, factors_df: pl.DataFrame) -> pl.DataFrame:
        """因子标准化：按accper分组做Z-score（(x-mean)/std），处理标准差为0的情况"""
        std_exprs = []
        for factor in self.factors:
            # 缓存分组均值和标准差（ddof=0：总体标准差）
            mean_col = pl.col(factor).mean().over('accper').alias(f"{factor}_mean")
            std_col = pl.col(factor).std(ddof=0).over('accper').alias(f"{factor}_std")
            
            # 标准化逻辑：标准差≠0则计算Z-score，否则填0
            std_factor_expr = pl.when(std_col != 0)\
            .then((pl.col(factor) - mean_col) / std_col)\
            .otherwise(0.0)\
            .alias(factor)
            
            std_exprs.extend([mean_col, std_col, std_factor_expr])
        
        # 执行标准化 + 删除临时列
        std_factors_df = factors_df.with_columns(std_exprs)
        std_factors_df = std_factors_df.drop(
            [f"{f}_mean" for f in self.factors] + [f"{f}_std" for f in self.factors]
        )
    
        return std_factors_df

    def _merge_and_fill_data(self, merged_df: pl.DataFrame) -> pl.DataFrame:
        """纵向合并历史数据 + 分组填充空值"""
        # 1. 纵向合并
        common_cols = ['stkcd', 'accper'] + self.factors + ['monthly_return']
        if self.latest_df is None:
            combined_df = merged_df.select(common_cols)
        else:
            # 合并前先对齐列顺序
            combined_df = self.latest_df.select(common_cols).vstack(merged_df.select(common_cols))
            
            # 按stkcd和accper去重（避免重复数据）
            combined_df = combined_df.unique(subset=['stkcd', 'accper'], keep='last')
        
        # 2. 分组，循环填充（先forward，后补0，按stkcd分组）
        # 填充因子: forward + 0
        clean_df = None
        for stkcd in combined_df['stkcd'].unique():
            stkcd_df = combined_df.filter(pl.col('stkcd') == stkcd).select(common_cols)
            clean_stk_df = stkcd_df.with_columns([
                pl.col(f).cast(pl.Float64, strict=False)  # 先转换为数值类型
                    .fill_nan(None)                    # 然后填充NaN
                    .fill_null(strategy='forward')
                    .fill_null(value=0)
                    .alias(f)
                for f in self.factors
            ])
            if clean_df is None:
                clean_df = clean_stk_df
            else:
                clean_df = clean_df.vstack(clean_stk_df)
        
        # 填充收益率：无风险收益  
        clean_df = clean_df.with_columns(
            pl.col('monthly_return')
                .cast(pl.Float64, strict=False)
                .fill_nan(None)
                .fill_null(self._risk_free_rate)
                .alias('monthly_return')
        )

        # 3. 过滤当前年份数据（仅保留处理的年度数据）
        clean_df = clean_df.filter(pl.col('accper').dt.year() == self.now_year)
        
        # 4. 校验填充结果
        null_counts = clean_df.select([pl.col(col).is_null().sum() for col in self.factors + ['monthly_return']])
        #logger.debug(f"填充后空值统计：{null_counts.to_dict()}")

        # 5.设置latest_df
        self.latest_df = clean_df
        
        return clean_df

    def _store_data_slices(self, clean_df: pl.DataFrame):
        """批量存储数据切片到Redis（替代逐行循环，提升性能）"""
        # 1. 预处理数据：按年份、月份、股票代码分组
        slice_data = clean_df.with_columns(
            pl.col('accper').dt.year().alias('year'),
            pl.col('accper').dt.month().alias('month')
        ).select(['year', 'month', 'stkcd', *self.factors, 'monthly_return'])
        
        # 2. 按(year, month, stkcd)分组，批量生成Redis键值对
        redis_pipeline = self.client.pipeline()  # 批量操作
        for row in slice_data.to_dicts():
            year = row.pop('year')
            month = row.pop('month')
            code = row.pop('stkcd')
            monthly_return = row.pop('monthly_return')
            
            # 按因子名排序，保证顺序一致
            sorted_factors = [v for k, v in sorted(row.items())]
            slice_value = json.dumps([sorted_factors, monthly_return])
            
            # 构建Redis键并加入管道（顺序：先计数器，后数据片）
            train_slice_key = REDIS_PREFIX_MANAGER.build_train_slice_key(year, month, code)
            counter_key = REDIS_PREFIX_MANAGER.build_counter_key(year, month, code)
            # 1. 先创建计数器（标记数据即将存在）
            redis_pipeline.set(counter_key, 0, ex=72000)
            # 2. 再创建数据片
            redis_pipeline.set(train_slice_key, slice_value, ex=72000)
        
        # 3. 执行批量写入
        redis_pipeline.execute()
        logger.info(f"年份{self.now_year}共存储{len(slice_data)}条数据切片")

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
            self.now_year = year
            
            try:
                factors_df, return_df = self._load_data_from_redis(year)
            except DataExpException as e:
                logger.warning(f'{e}, 跳过')
                return 
            
            # 2.因子标准化（按 accper 分组，对每个因子进行 z-score 标准化）
            # 标准化公式: (x - mean) / std
            # 需要保留所有行和列，只标准化因子列
            # 按 accper 分组，对每个因子列进行标准化
            # 使用 over() 窗口函数，保留所有行
            std_factors_df = self._standardize_factors(factors_df)

            # 3.连接因子和收益率（收益率的日期滞后一月,1月的因子数据与2月的收益率数据连接）    
            return_df = return_df.with_columns(
                pl.col('accper').dt.offset_by('-1mo').alias('accper')
            )
            merged_df:pl.DataFrame = std_factors_df.join(return_df, on=['stkcd','accper'], how='left')

            # 4.纵向合并df，进行填充（如果latest_df不存在，则使用向前-向后-补0三步骤填充）
            clean_df = self._merge_and_fill_data(merged_df)
            self.latest_df = clean_df

            # 5.将数据处理为数据片  
            self._store_data_slices(clean_df)

            # 6.移除当前year的df
            self.client.set(REDIS_PREFIX_MANAGER.build_deleted_df_year_key(self.now_year), 1, ex = 72000)
            self.client.delete(REDIS_PREFIX_MANAGER.build_df_key(self.now_year,'factors_df'))
            self.client.delete(REDIS_PREFIX_MANAGER.build_df_key(self.now_year,'return_df'))
            

            # 7.发布事件  
            MESSAGE_BUS.publish(
                message = TrainDataUpdatedMessage(
                    message_type = 'train_data_updated',
                    publisher = 'TrainDataUpdater',
                    payload = TrainDataUpdatedPayload(
                        request_id = message['payload']['request_id'],
                        year = self.now_year,
                        first = self.first  
                    )
                )
            )
            
            if self.first:
                self.first = False # 第一次发布后，设置为False  


    def _subscribe(self):
        MESSAGE_BUS.subscribe(
            message_type='data_loaded',
            handler=self.data_loaded_handler
        )

TRAIN_DATA_UPDATER = TrainDataUpdater()

