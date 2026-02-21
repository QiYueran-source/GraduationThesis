#!/usr/bin/env python3
"""
测试 code_list.py 中的各个功能
运行方式：python test_code_list.py
"""

import sys
import os
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置路径（与项目一致）
import src.utils.set.set_pypath

# 导入被测试模块
from src.manager.database.code_list import (
    get_code_list,
    read_db_to_get_code_list,
    _get_all_code_list,
    _get_return_stats,
    _get_fin_code_list,
    _get_st_code_list,
    segment_num,
    segment_cursor,
    segment_seed,
)

# 日志
from src.utils.logger import get_module_logger
logger = get_module_logger(__name__, '[TestCodeList]')


def test_get_all_code_list():
    """测试获取所有股票代码列表"""
    print("=== 测试 _get_all_code_list ===")
    try:
        codes = _get_all_code_list()
        print(f"✅ 获取到 {len(codes)} 只股票")
        print(f"前10只: {codes[:10]}")
        print(f"后10只: {codes[-10:]}")

        # 检查是否有重复
        if len(codes) != len(set(codes)):
            print("❌ 发现重复代码")
        else:
            print("✅ 无重复代码")

        # 检查格式（6位数字）
        invalid_codes = [c for c in codes if not (isinstance(c, str) and len(c) == 6 and c.isdigit())]
        if invalid_codes:
            print(f"❌ 发现 {len(invalid_codes)} 个格式不正确的代码: {invalid_codes[:5]}")
        else:
            print("✅ 所有代码格式正确")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

    return True


def test_get_return_stats():
    """测试获取收益率统计"""
    print("\n=== 测试 _get_return_stats ===")
    try:
        # 测试无参数
        df = _get_return_stats()
        print(f"✅ 获取到 {len(df)} 行统计数据")
        print(f"列名: {df.columns}")
        print(f"前5行:\n{df.head(5)}")

        # 检查必要列
        required_cols = ['stkcd', 'data_completeness_pct', 'total_months', 'valid_returns']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"❌ 缺少必要列: {missing_cols}")
            return False

        # 测试带参数
        test_codes = ['000001', '000002', '000003']
        df_filtered = _get_return_stats(stkcd_list=test_codes)
        print(f"✅ 过滤后剩余 {len(df_filtered)} 行")
        if len(df_filtered) > len(test_codes):
            print("❌ 过滤结果过多，可能有问题")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

    return True


def test_get_fin_code_list():
    """测试获取金融股票列表"""
    print("\n=== 测试 _get_fin_code_list ===")
    try:
        fin_codes = _get_fin_code_list()
        print(f"✅ 获取到 {len(fin_codes)} 只金融股票")
        print(f"样本: {fin_codes[:10]}")

        # 检查格式
        invalid_codes = [c for c in fin_codes if not (isinstance(c, str) and len(c) == 6 and c.isdigit())]
        if invalid_codes:
            print(f"❌ 发现 {len(invalid_codes)} 个格式不正确的金融代码: {invalid_codes[:5]}")
            return False
        else:
            print("✅ 金融代码格式正确")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

    return True


def test_get_st_code_list():
    """测试获取 ST 股票列表"""
    print("\n=== 测试 _get_st_code_list ===")
    try:
        st_codes = _get_st_code_list()
        print(f"✅ 获取到 {len(st_codes)} 只 ST 股票")
        print(f"样本: {st_codes[:10]}")

        # 检查格式
        invalid_codes = [c for c in st_codes if not (isinstance(c, str) and len(c) == 6 and c.isdigit())]
        if invalid_codes:
            print(f"❌ 发现 {len(invalid_codes)} 个格式不正确的 ST 代码: {invalid_codes[:5]}")
            return False
        else:
            print("✅ ST 代码格式正确")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

    return True


def test_read_db_to_get_code_list():
    """测试 read_db_to_get_code_list 各种模式"""
    print("\n=== 测试 read_db_to_get_code_list ===")

    test_cases = [
        ('test', '测试模式'),
        ('all', '全市场模式'),
        ('balance', '平衡面板模式'),
        ('clean', '数据质量筛选模式'),
        ('balance_and_clean', '平衡+质量筛选模式')
    ]

    for code_type, description in test_cases:
        try:
            print(f"\n--- 测试 {description} ({code_type}) ---")
            codes = read_db_to_get_code_list()  # 注意：这个函数使用全局配置中的 pool_type

            print(f"✅ {description} 获取到 {len(codes)} 只股票")
            print(f"前5只: {codes[:5]}")

            # 检查格式
            invalid_codes = [c for c in codes if not (isinstance(c, str) and len(c) == 6 and c.isdigit())]
            if invalid_codes:
                print(f"❌ {description} 发现 {len(invalid_codes)} 个格式不正确的代码")
                return False

            # 检查是否有重复
            if len(codes) != len(set(codes)):
                print(f"❌ {description} 发现重复代码")
                return False

        except Exception as e:
            print(f"❌ {description} 测试失败: {e}")
            return False

    return True


def test_code_list_counts():
    """当前配置下：不分段与分段分别展示 get_code_list 能获得多少代码"""
    print("\n=== 当前配置下代码数量（不分段 vs 分段） ===")
    try:
        # 不分段：完整列表（read_db_to_get_code_list 不应用 segment 逻辑）
        full_list = read_db_to_get_code_list()
        full_count = len(full_list)
        print(f"不分段（完整列表）: {full_count} 只")

        # 分段：get_code_list() 会按 stock_pool 的 segment_* 打乱并取当前段
        segmented_list = get_code_list()
        segmented_count = len(segmented_list)
        print(f"分段（当前配置）: {segmented_count} 只")
        print(f"  配置: segment_num={segment_num}, segment_cursor={segment_cursor}, segment_seed={segment_seed}")

        if segment_num > 1 and full_count > 0:
            expected_per_segment = full_count // segment_num
            print(f"  说明: 共 {segment_num} 段，当前为第 {segment_cursor} 段，约每段 {expected_per_segment}～{expected_per_segment + 1} 只")
        print("✅ 代码数量展示完成")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    return True


def test_get_code_list():
    """测试 get_code_list 主入口"""
    print("\n=== 测试 get_code_list 主入口 ===")

    try:
        codes = get_code_list()
        print(f"✅ get_code_list 获取到 {len(codes)} 只股票")
        print(f"前5只: {codes[:5]}")

        # 检查格式和唯一性
        invalid_codes = [c for c in codes if not (isinstance(c, str) and len(c) == 6 and c.isdigit())]
        if invalid_codes:
            print(f"❌ 发现 {len(invalid_codes)} 个格式不正确的代码")
            return False

        if len(codes) != len(set(codes)):
            print("❌ 发现重复代码")
            return False

        print("✅ get_code_list 测试通过")

    except Exception as e:
        print(f"❌ get_code_list 测试失败: {e}")
        return False

    return True


def test_filtering_logic():
    """测试过滤逻辑"""
    print("\n=== 测试过滤逻辑 ===")

    try:
        # 获取原始列表
        all_codes = _get_all_code_list()
        print(f"原始股票总数: {len(all_codes)}")

        # 获取过滤列表
        filtered_codes = read_db_to_get_code_list()
        print(f"过滤后股票总数: {len(filtered_codes)}")

        # 检查过滤是否生效
        if len(filtered_codes) >= len(all_codes):
            print("⚠️ 过滤后数量没有减少，可能过滤未生效")

        # 检查过滤列表是否为原始列表的子集
        filtered_set = set(filtered_codes)
        all_set = set(all_codes)
        if not filtered_set.issubset(all_set):
            print("❌ 过滤结果包含原始列表外的股票")
            return False

        print("✅ 过滤逻辑测试通过")

    except Exception as e:
        print(f"❌ 过滤逻辑测试失败: {e}")
        return False

    return True


def run_all_tests():
    """运行所有测试"""
    print("开始测试 code_list.py 功能...")
    print("=" * 50)

    test_results = [
        test_get_all_code_list(),
        test_get_return_stats(),
        test_get_fin_code_list(),
        test_get_st_code_list(),
        test_read_db_to_get_code_list(),
        test_code_list_counts(),
        test_get_code_list(),
        test_filtering_logic()
    ]

    print("\n" + "=" * 50)
    passed = sum(test_results)
    total = len(test_results)
    print(f"测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！")
        return True
    else:
        print("❌ 部分测试失败，请检查上述输出")
        return False


if __name__ == "__main__":
    try:
        success = test_code_list_counts()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n用户中断测试")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中发生未预期的错误: {e}")
        sys.exit(1)