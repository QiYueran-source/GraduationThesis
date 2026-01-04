import src.set_pypath
import src.manager.database.factors
import datetime as dt

factors_data = src.manager.database.factors.get_factors_data(
    code_list = ['000001','000002'],
    start_date = dt.date(2019, 1, 1),
    end_date = dt.date(2020, 12, 31)
)
print(factors_data)

from src.manager.database.stock_return import read_return
return_data = read_return(
    code_list = ['000001','000002'],
    start_date = dt.date(2019, 1, 1),
    end_date = dt.date(2020, 12, 31)
)
print(return_data)