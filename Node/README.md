# 节点

节点使用docker打包到其他主机上运行

## 1. frp配置

### 解压frp
```bash
# 解压已下载的frp文件
mkdir -p frp
tar -xzf frp_0.65.0_linux_amd64.tar.gz -C frp --strip-components=1
chmod +x frp/frpc frp/frps
```

### 配置frpc.ini
修改 `frp/frpc.ini` 中的服务器信息：
- `server_addr`: frp服务器IP地址
- `server_port`: frp服务器端口（默认7000）
- `token`: 连接令牌
- `remote_port`: 远程访问端口

## 2. frp独立管理

### 启动frp客户端
```bash
./scripts/frp_start.sh
```

### 停止frp客户端
```bash
./scripts/frp_stop.sh
```

### 检查frp状态
```bash
./scripts/frp_status.sh
```

## 4. 本地开发启动

### 一键启动
```bash
./scripts/start_with_frp.sh
```

### 单独启动
```bash
# 启动frp
./scripts/frp_start.sh

# 启动worker
python worker.py
```

### 停止服务
```bash
./scripts/stop.sh
```

### 检查状态
```bash
./scripts/status.sh
```

## 5. Docker部署

```bash
# 构建镜像
docker build -f DockerFile -t graduation-thesis-node .

# 运行容器
docker run -d --name node-agent graduation-thesis-node
```

## 6. 目录结构

```
Node/
├── frp/                    # frp文件目录
│   ├── frpc               # frp客户端
│   ├── frps               # frp服务端
│   └── frpc.ini          # 配置文件
├── scripts/               # 管理脚本
│   ├── frp_start.sh      # frp启动脚本
│   ├── frp_stop.sh       # frp停止脚本
│   ├── frp_status.sh     # frp状态检查
│   ├── start_with_frp.sh # 一键启动
│   ├── stop.sh           # 停止服务
│   └── status.sh         # 状态检查
├── src/                   # 源代码
├── logs/                  # 日志目录
├── worker.py             # 工作进程
├── DockerFile            # Docker构建文件
└── README.md             # 说明文档
```

