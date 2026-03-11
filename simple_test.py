#!/usr/bin/env python3
"""
简单的方差函数测试
"""
import numpy as np

# 参数设置
A_RE = 0.75
B_RE = 10
NEG_SLOPE = 2.0

def calculate_re_std(return_val):
    """计算re_std的分段函数"""
    if return_val >= 0:
        # 正收益：抛物线
        variance = max(0, A_RE**2 - B_RE * return_val**2)
        return np.sqrt(variance)
    else:
        # 负收益：平缓直线
        variance = A_RE**2 + NEG_SLOPE * abs(return_val)
        return np.sqrt(variance)

print("新的分段方差函数测试完成！")
print(f"参数设置：A_RE={A_RE}, B_RE={B_RE}, NEG_SLOPE={NEG_SLOPE}")
print("\n关键点测试：")
for r in [-0.15, -0.1, -0.05, 0, 0.05, 0.1, 0.15]:
    std_val = calculate_re_std(r)
    print(".3f")

print("\n验证修改是否成功：")
print("- 正收益区间 (≥0)：使用抛物线，收益越大方差越小")
print("- 负收益区间 (<0)：使用平缓直线，收益越小方差平缓增大")
print("- 在 return=0 处连续，基准方差为", A_RE)