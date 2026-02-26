"""
多轮训练编排：按年/段修改 hyparam，每轮以子进程执行 run_session.py。
KBI 时调用 scripts/stop.sh 停节点并删除 Redis gt:*；每轮结束后删除当日日志。
"""
import subprocess
import sys
import time
from pathlib import Path

from src.utils.set import set_pypath
set_pypath()

import yaml

from src.manager.redis import REDIS_PREFIX_MANAGER, REDIS_CONNECTOR

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "hyparam.yaml"
SESSION_SCRIPT = PROJECT_ROOT / "run_session.py"
STOP_SCRIPT = PROJECT_ROOT / "scripts" / "stop.sh"

YEARS = list(range(2004, 2024))
END_YEAR = 2024  # 训练结束年，每轮从 start_year 训练到 end_year
SEGMENT_NUM = 1
META_SEED = 43
SEGMENT_SEED = 43
SAMPLE_AND_SHUFFLE_SEED = 153


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def delete_gt_keys():
    client = REDIS_CONNECTOR.get_client()
    prefix = REDIS_PREFIX_MANAGER.project_prefix
    pattern = f"{prefix}*"
    deleted = 0
    try:
        for key in client.scan_iter(match=pattern):
            client.delete(key)
            deleted += 1
        if deleted:
            print(f"已删除 Redis 键 {deleted} 个（pattern={pattern}）")
    except Exception as e:
        print(f"删除 Redis 键异常: {e}")


def run_stop_script():
    try:
        subprocess.run(
            [str(STOP_SCRIPT)],
            cwd=PROJECT_ROOT,
            shell=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("scripts/stop.sh 执行超时")
    except Exception as e:
        print(f"执行 scripts/stop.sh 失败: {e}")


def delete_today_log():
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = PROJECT_ROOT / "logs" / f"app_{date_str}.log"
    if log_path.exists():
        try:
            log_path.unlink()
            print(f"已删除日志: {log_path}")
        except Exception as e:
            print(f"删除日志失败: {e}")


def main():
    try:
        cfg = load_config()
        cfg["stock_pool"]["segment_cursor"] = 1
        cfg["meta"]["checkpoint"] = False
        cfg["meta"]["start_year"] = 2004
        cfg["meta"]["end_year"] = END_YEAR
        cfg["meta_seed"] = META_SEED
        cfg["stock_pool"]["segment_seed"] = SEGMENT_SEED
        cfg["meta"]["env_config"]["sample_and_shuffle_seed"] = SAMPLE_AND_SHUFFLE_SEED
        save_config(cfg)

        for year in YEARS:
            cfg = load_config()
            cfg["meta"]["start_year"] = year
            cfg["meta"]["end_year"] = END_YEAR
            cfg["stock_pool"]["increment"] = False if year == 2004 else (year - 1)
            cfg["stock_pool"]["segment_num"] = SEGMENT_NUM
            save_config(cfg)

            for cursor in range(1, SEGMENT_NUM + 1):
                cfg = load_config()
                cfg["stock_pool"]["segment_cursor"] = cursor
                cfg["meta"]["checkpoint"] = not (year == 2004 and cursor == 1)
                save_config(cfg)

                print(f"  年={year} segment={cursor}/{SEGMENT_NUM} checkpoint={cfg['meta']['checkpoint']}")
                print("当前轮配置:")
                print(cfg)

                proc = subprocess.Popen(
                    [sys.executable, str(SESSION_SCRIPT)],
                    cwd=PROJECT_ROOT,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )

                try:
                    proc.wait()
                except KeyboardInterrupt:
                    print("\n收到 Ctrl+C，停止节点并清理 Redis...")
                    run_stop_script()
                    delete_gt_keys()
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                    raise

                delete_today_log()
                time.sleep(60) # 等待全部完成

        print("\n========== 2004→2024 单轮全部完成 ==========")
    except KeyboardInterrupt:
        print("已退出")
    finally:
        pass


if __name__ == "__main__":
    main()
