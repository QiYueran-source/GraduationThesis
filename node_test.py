"""
NodeManager 测试脚本
- 加载配置、清空端口、获取可用/运行中端口
- 生成 meta 列表（共享 task_id）
- 可选：向节点下发任务启动
- 测试新接口：get_all_status, get_all_available_port, get_all_running_task_port
- 测试监控器：start_monitor, stop_monitor
"""
import uuid 
import time
import json
import src.utils.set.set_pypath

from src.manager.service.node_manager import NodeManager
from src.manager.redis import REDIS_CONNECTOR, REDIS_PREFIX_MANAGER


def main():
    nm = NodeManager()

    # 1. 清空端口池（可选，依赖清空服务）
    print("=== 1. clear_ports ===")
    ok = nm.clear_ports()
    print(f"clear_ports: {ok}\n")

    # 2. 获取可用端口（旧接口）
    print("=== 2. get_available_ports (旧接口) ===")
    try:
        available = nm.get_available_ports()
        print(f"可用端口数: {len(available)}, 端口: {available}\n")
    except AttributeError:
        print("get_available_ports 方法不存在，跳过\n")
        available = []

    # 3. 测试新接口：get_all_status
    print("=== 3. get_all_status (新接口) ===")
    all_status = nm.get_all_status()
    print(f"查询到 {len(all_status)} 个节点状态")
    if all_status:
        # 显示前3个节点的状态
        for i, (port, status) in enumerate(list(all_status.items())[:3]):
            print(f"  端口 {port}: running={status.get('running')}, "
                  f"task_id={status.get('task_id')}, "
                  f"node_id={status.get('node_id')}, "
                  f"current_year_month={status.get('current_year_month')}")
    print()

    # 4. 测试新接口：get_all_available_port
    print("=== 4. get_all_available_port (新接口) ===")
    available_ports = nm.get_all_available_port()
    print(f"可用端口数: {len(available_ports)}, 端口: {available_ports}\n")

    # 5. 生成 meta 列表（共享 task_id）
    task_id = "test" + str(uuid.uuid4())
    num = max(1, min(3, len(available_ports) if available_ports else 1))  # 1~3 条
    print(f"=== 5. generate_node_meta(num={num}, task_id={task_id}) ===")
    meta_list = nm.generate_node_meta(num=num, task_id=task_id)
    print(f"生成 meta 数: {len(meta_list)}")
    if meta_list:
        m = meta_list[0]
        print(f"首条 meta 键: {list(m.keys())}")
        print(f"  task_id: {m.get('task_id')}")
        print(f"  start_year, end_year: {m.get('start_year')}, {m.get('end_year')}")
        print(f"  N, len(stock_list): {m.get('N')}, {len(m.get('stock_list', []))}")
        print(f"  train_config 键: {list(m.get('train_config', {}).keys())}\n")

    # 6. 启动节点（向可用端口下发 meta；无节点时会报失败，属正常）
    print("=== 6. start_nodes ===")
    if meta_list:
        ok_count, fail_count = nm.start_nodes(meta_list)
        print(f"启动结果: 成功 {ok_count}, 失败 {fail_count}\n")
        
        # 等待一下让节点启动
        if ok_count > 0:
            print("等待 5 秒让节点启动...")
            time.sleep(5)
            
            # 7. 测试新接口：get_all_running_task_port
            print(f"=== 7. get_all_running_task_port(task_id={task_id}) ===")
            running_ports = nm.get_all_running_task_port(task_id)
            print(f"运行 task_id={task_id} 的端口数: {len(running_ports)}, 端口: {running_ports}\n")
    else:
        print("无 meta，跳过 start_nodes\n")

    # 8. 测试监控器
    print("=== 8. 测试节点监控器 ===")
    print("启动监控器...")
    nm.start_monitor()
    print("监控器已启动，等待 120 秒让监控器执行一次完整循环...")
    time.sleep(120)
    
    # 检查 Redis 中的节点信息
    redis_client = REDIS_CONNECTOR.get_client()
    node_info_key = REDIS_PREFIX_MANAGER.build_node_info_key()
    node_info = redis_client.hgetall(node_info_key)
    
    print(f"Redis 中的节点信息 (键: {node_info_key}):")
    if node_info:
        print(f"  node_num: {node_info.get('node_num', 'N/A')}")
        print(f"  last_update: {node_info.get('last_update', 'N/A')}")
        
        # 显示 task_id 相关的信息
        task_keys = [k for k in node_info.keys() if k.startswith('task_')]
        for key in task_keys:
            if key.endswith('_count'):
                print(f"  {key}: {node_info[key]}")
            elif key.endswith('_nodes'):
                try:
                    nodes = json.loads(node_info[key])
                    print(f"  {key}: {len(nodes)} 个节点")
                    if nodes:
                        print(f"    示例节点: {nodes[0]}")
                except json.JSONDecodeError:
                    print(f"  {key}: JSON 解析失败")
    else:
        print("  无节点信息（可能还没有节点运行）")
    print()
    
    # 停止监控器
    print("停止监控器...")
    nm.stop_monitor(timeout=5.0)
    print("监控器已停止\n")

    print("node_test 完成.")


if __name__ == "__main__":
    main()
