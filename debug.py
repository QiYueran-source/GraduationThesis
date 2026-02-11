import polars as pl

df = pl.DataFrame({
    'stkcd': ['000001', '000002', '000003','000001', '000002', '000003','000001', '000002', '000003'],
    'accper': ['2020-01-01', '2020-02-01', '2020-03-01','2020-01-01', '2020-02-01', '2020-03-01','2020-01-01', '2020-02-01', '2020-03-01'],
    'f1': [1, None, 3,1, None, 3,1, None, 3],
    'f2': [4, 5, None,4, 5, None,4, 5, None],
    'f3': [None, 8, 9,None, 8, 9,None, 8, 9],
    'monthly_return': [None, None, None,None, None, None,None, None, None]
})

print(df)
# 2. 分组，循环填充（先forward，后补0，按stkcd分组）
clean_df = None
for stkcd in df['stkcd'].unique():
    stkcd_df = df.filter(pl.col('stkcd') == stkcd).select(['stkcd', 'accper', 'f1', 'f2', 'f3', 'monthly_return'])
    clean_stk_df = stkcd_df.with_columns([
    pl.col(f).cast(pl.Float64, strict=False)  # 先转换为数值类型
            .fill_nan(None)                    # 然后填充NaN
            .fill_null(strategy='forward')
            .fill_null(value=0)
            .alias(f) 
        for f in ('f1', 'f2', 'f3', 'monthly_return')
    ])
    if clean_df is None:
        clean_df = clean_stk_df
    else:
        clean_df = clean_df.vstack(clean_stk_df)

print(clean_df)