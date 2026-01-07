# 端口池管理系统

## 📋 服务简介

这是一个基于Flask开发的端口池管理系统，用于动态分配和释放端口资源。系统维护一个可用端口队列和已分配端口集合，支持端口的重复利用和管理。

## ✨ 功能特性

- 🚀 **动态分配**：从可用端口队列中FIFO方式分配端口
- 🔄 **重复利用**：释放的端口可以重新分配使用
- 🎯 **精确释放**：支持释放指定的端口号
- 🧹 **批量清空**：可以清空所有已分配的端口
- 📊 **状态监控**：实时查看端口使用情况
- 🛡️ **错误处理**：完善的错误提示和状态检查

## 🔧 技术栈

- **Python 3.6+**
- **Flask 2.x**
- **端口范围**：8191-8220（可配置）

## 📚 API接口文档

### 基础信息
- **服务端口**：8190
- **Content-Type**：application/json
- **响应格式**：JSON

---

### 1. 分配端口
**接口**: `GET /register`

**功能**: 从可用端口队列中分配一个端口

**请求示例**:
```bash
curl -X GET http://localhost:8190/register
```

**成功响应**:
```json
{
  "status": "success",
  "allocated_port": 8191,
  "available_count": 29,
  "allocated_count": 1
}
```

**错误响应**:
```json
{
  "error": "没有可用端口",
  "status": "no_port"
}
```

---

### 2. 释放端口
**接口**: `DELETE /release/{port}`

**功能**: 释放指定的端口号

**请求示例**:
```bash
curl -X DELETE http://localhost:8190/release/8191
```

**成功响应**:
```json
{
  "status": "released",
  "released_port": 8191,
  "available_count": 30,
  "allocated_count": 0
}
```

**错误响应**:
```json
{
  "error": "端口 8191 未被分配",
  "status": "not_allocated"
}
```

---

### 3. 清空所有分配
**接口**: `DELETE /clear`

**功能**: 将所有已分配的端口移回可用队列

**请求示例**:
```bash
curl -X DELETE http://localhost:8190/clear
```

**成功响应**:
```json
{
  "status": "cleared",
  "released_count": 5,
  "available_count": 30,
  "allocated_count": 0
}
```

---

### 4. 查看状态
**接口**: `GET /status`

**功能**: 查看当前端口池状态

**请求示例**:
```bash
curl -X GET http://localhost:8190/status
```

**响应示例**:
```json
{
  "available_count": 28,
  "allocated_count": 2,
  "available_ports": [8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200, 8201, 8202],
  "allocated_ports": [8191, 8192],
  "port_range": "8191-8220",
  "total_ports": 30
}
```

---

### 5. 健康检查
**接口**: `GET /health`

**功能**: 服务健康状态检查

**请求示例**:
```bash
curl -X GET http://localhost:8190/health
```

**响应示例**:
```json
{
  "status": "ok",
  "service": "port-pool-manager",
  "port": 8190,
  "port_range": "8191-8220",
  "available_count": 30,
  "allocated_count": 0
}
```

## 🚀 使用示例

### 基本使用流程

```bash
# 1. 启动服务
python3 checkapp.py

# 2. 分配端口给节点1
curl http://localhost:8190/register
# 返回: {"allocated_port": 8191, ...}

# 3. 分配端口给节点2
curl http://localhost:8190/register
# 返回: {"allocated_port": 8192, ...}

# 4. 查看当前状态
curl http://localhost:8190/status

# 5. 节点1完成任务，释放端口
curl -X DELETE http://localhost:8190/release/8191

# 6. 分配新端口给节点3（复用已释放的端口）
curl http://localhost:8190/register
# 返回: {"allocated_port": 8191, ...}  # 复用了8191

# 7. 任务完成，清空所有分配
curl -X DELETE http://localhost:8190/clear
```

### Python客户端示例

```python
import requests

class PortManager:
    def __init__(self, base_url="http://localhost:8190"):
        self.base_url = base_url

    def allocate_port(self):
        """分配端口"""
        response = requests.get(f"{self.base_url}/register")
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                return data['allocated_port']
        return None

    def release_port(self, port):
        """释放端口"""
        response = requests.delete(f"{self.base_url}/release/{port}")
        return response.status_code == 200

    def clear_all(self):
        """清空所有分配"""
        response = requests.delete(f"{self.base_url}/clear")
        return response.status_code == 200

    def get_status(self):
        """获取状态"""
        response = requests.get(f"{self.base_url}/status")
        return response.json() if response.status_code == 200 else None

# 使用示例
pm = PortManager()
port = pm.allocate_port()
print(f"Allocated port: {port}")

# 任务完成后释放
pm.release_port(port)
```

## 📦 部署说明

### 环境要求
- Python 3.6+
- Flask 2.x

### 安装依赖
```bash
pip install flask
```

### 启动服务
```bash
# 开发环境
python3 checkapp.py

# 生产环境（推荐）
gunicorn --bind 0.0.0.0:8190 --workers 4 checkapp:app
```

### 配置说明
- **端口范围**：在代码中修改 `PORT_RANGE_START` 和 `PORT_RANGE_END`
- **服务端口**：修改 `app.run(port=8190)` 中的端口号

## 🔍 监控和调试

### 查看实时状态
```bash
# 每秒查看一次状态
watch -n 1 'curl -s http://localhost:8190/status | jq ".allocated_count, .available_count"'
```

### 日志监控
服务会在控制台输出端口分配和释放的日志信息。

## ⚠️ 注意事项

1. **端口冲突**：系统会检查端口是否被其他进程占用
2. **内存存储**：重启服务后所有分配记录会丢失
3. **并发安全**：Flask默认是线程安全的，但高并发场景建议使用Gunicorn
4. **端口范围**：确保配置的端口范围可用且不与其他服务冲突

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 📄 许可证

MIT License
