import os 
import sys 

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 添加项目根目录到Python路径
sys.path.append(PROJECT_ROOT)

# 添加src目录到Python路径
sys.path.append(os.path.join(PROJECT_ROOT, 'src'))
