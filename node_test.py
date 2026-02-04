"""
NodeManager 测试脚本
- 加载配置、清空端口、获取可用/运行中端口
- 生成 meta 列表（共享 task_id）
- 可选：向节点下发任务启动
"""
import src.utils.set.set_pypath

from src.manager.service.node_manager import NodeManager


def main():
    nm = NodeManager()

    # 1. 清空端口池（可选，依赖清空服务）
    print("=== 1. clear_ports ===")
    ok = nm.clear_ports()
    print(f"clear_ports: {ok}\n")

    # 2. 获取可用端口
    print("=== 2. get_available_ports ===")
    available = nm.get_available_ports()
    print(f"可用端口数: {len(available)}, 端口: {available}\n")

    # 3. 获取正在运行的端口
    print("=== 3. get_running_ports ===")
    running = nm.get_running_ports()
    print(f"正在运行端口数: {len(running)}, 端口: {running}\n")

    # 4. 生成 meta 列表（共享 task_id）
    task_id = "test_006"
    num = max(1, min(3, len(available)))  # 1~3 条，不超过可用端口数
    print(f"=== 4. generate_node_meta(num={num}, task_id={task_id}) ===")
    meta_list = nm.generate_node_meta(num=num, task_id=task_id)
    print(f"生成 meta 数: {len(meta_list)}")
    if meta_list:
        m = meta_list[0]
        print(f"首条 meta 键: {list(m.keys())}")
        print(f"  task_id: {m.get('task_id')}")
        print(f"  start_year, end_year, end_month: {m.get('start_year')}, {m.get('end_year')}, {m.get('end_month')}")
        print(f"  N, len(stock_list): {m.get('N')}, {len(m.get('stock_list', []))}")
        print(f"  train_config 键: {list(m.get('train_config', {}).keys())}\n")

    # 5. 启动节点（向可用端口下发 meta；无节点时会报失败，属正常）
    print("=== 5. start_nodes ===")
    if meta_list:
        ok_count, fail_count = nm.start_nodes(meta_list)
        print(f"启动结果: 成功 {ok_count}, 失败 {fail_count}\n")
    else:
        print("无 meta，跳过 start_nodes\n")

    print("node_test 完成.")


if __name__ == "__main__":
    main()
