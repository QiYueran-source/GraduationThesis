#!/usr/bin/env python3
"""
TCP服务器测试脚本
监听4321端口，接收TCP连接并打印收到的消息
"""
import socket
import sys

def main():
    # 创建TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # 绑定到本地4321端口
    host = '127.0.0.1'
    port = 4321
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"[INFO] TCP服务器启动，监听 {host}:{port}")
        print(f"[INFO] 等待连接和消息...")
        print(f"[INFO] 可以通过 frp 远程端口 8195 访问")
        
        while True:
            # 接受连接
            client_socket, client_address = server_socket.accept()
            print(f"[INFO] 收到来自 {client_address} 的连接")
            
            # 接收数据
            try:
                data = client_socket.recv(1024)
                if data:
                    message = data.decode('utf-8', errors='ignore').strip()
                    print(f"[收到消息] {message}")
                    
                    # 可选：发送确认响应
                    response = f"已收到: {message}\n"
                    client_socket.send(response.encode('utf-8'))
                    print(f"[INFO] 已发送确认响应")
                
            except Exception as e:
                print(f"[ERROR] 处理连接时出错: {e}")
            finally:
                client_socket.close()
                print(f"[INFO] 连接已关闭\n")
                
    except KeyboardInterrupt:
        print("\n[INFO] 服务器关闭")
    except Exception as e:
        print(f"[ERROR] 服务器错误: {e}")
        sys.exit(1)
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()