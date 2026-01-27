from src.manager.redis import REDIS_CONNECTOR

def start_protect():
    """开启 Redis 保护模式"""
    try:
        client = REDIS_CONNECTOR.get_client()
        client.config_set('protected-mode', 'yes')
        print("✅ Redis 保护模式已开启")
        return True
    except Exception as e:
        print(f"❌ 开启保护模式失败: {e}")
        return False

def stop_protect():
    """关闭 Redis 保护模式"""
    try:
        client = REDIS_CONNECTOR.get_client()
        client.config_set('protected-mode', 'no')
        print("✅ Redis 保护模式已关闭")
        return True
    except Exception as e:
        print(f"❌ 关闭保护模式失败: {e}")
        return False