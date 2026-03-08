# Game Host 使用说明

## 目录结构

```
game-host/
├── Dockerfile              # Docker 镜像构建文件
├── requirements.txt        # Python 依赖
├── main.py                 # 主程序
├── saiblo_protocol.py      # Saiblo 通信协议
├── thuai8_client.py        # THUAI8 gRPC 客户端
├── message_pb2.py          # 从后端复制
├── message_pb2_grpc.py     # 从后端复制
└── README.md               # 本文件
```

## 准备工作

### 1. 确认默认配置

在 `thuai8_client.py` 中的 `get_default_piece_config()` 函数需要与后端确认：

```python
def get_default_piece_config(player_id: int) -> list:
    # TODO: 需要与后端确认默认配置
    return [
        {
            "strength": 10,
            "intelligence": 10,
            "dexterity": 10,
            "equip": {"x": 0, "y": 0},
            "pos": {"x": 9, "y": 6}  # 需要确认
        }
    ]
```

### 2. 确认胜利条件

在 `main.py` 中的 `determine_winner()` 函数需要与后端确认：

```python
def determine_winner(self, grpc_state) -> int:
    # TODO: 需要与后端确认胜利条件
    pass
```

## 本地测试

### 方式1：直接运行（需要 THUAI8 Server 已启动）

```bash
# 1. 启动 THUAI8 Server
cd ../thuai8-backend/server
dotnet run --urls http://localhost:50051

# 2. 在另一个终端运行 Game Host
cd game-host
python main.py
```

然后手动通过 stdin 发送消息进行测试。

### 方式2：使用测试脚本

创建 `test_game_host.py`:

```python
import subprocess
import struct
import json
import time

def send_message(proc, data):
    content = json.dumps(data).encode('utf-8')
    length = struct.pack('>I', len(content))
    proc.stdin.write(length + content)
    proc.stdin.flush()

def read_message(proc):
    length_bytes = proc.stdout.read(4)
    length = struct.unpack('>I', length_bytes)[0]
    data = proc.stdout.read(length)
    return json.loads(data.decode('utf-8'))

# 启动 Game Host
proc = subprocess.Popen(
    ['python', 'main.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE
)

# 发送初始化消息
send_message(proc, {
    "player_list": [1, 1],
    "replay": "/tmp/test_replay.json",
    "config": {"random_seed": 12345}
})

# 读取回合配置
config = read_message(proc)
print("Config:", config)

# ... 继续测试
```

## Docker 构建

### 1. 构建镜像

```bash
docker build -t thuai8-game-host:test .
```

### 2. 测试镜像

```bash
docker run -it --rm thuai8-game-host:test
```

## 与 Saiblo Worker 集成

### 1. 推送镜像到仓库

```bash
# 标记镜像
docker tag thuai8-game-host:test ghcr.io/your-org/thuai8-game-host:1.0.0

# 推送
docker push ghcr.io/your-org/thuai8-game-host:1.0.0
```

### 2. 配置 Saiblo Worker

创建 `saiblo-worker-compose.yml`:

```yaml
version: '3.8'

services:
  gateway:
    image: alpine/socat:latest
    command: -d -d tcp-listen:443,fork,reuseaddr tcp-connect:server.saiblo.net:443
    networks:
      default:
      internal:
        aliases:
          - api.saiblo.net

  saiblo-worker:
    image: ghcr.io/thuasta/saiblo-worker:0.4.4
    depends_on:
      - gateway
    environment:
      NAME: thuai8-worker
      GAME_HOST_IMAGE: ghcr.io/your-org/thuai8-game-host:1.0.0
      GAME_HOST_CPUS: 2
      GAME_HOST_MEM_LIMIT: 4g
      HTTP_BASE_URL: https://api.saiblo.net
      WEBSOCKET_URL: wss://api.saiblo.net/ws/
      JUDGE_TIMEOUT: 1800
    networks:
      internal:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

networks:
  default:
  internal:
    internal: true
```

### 3. 启动 Saiblo Worker

```bash
docker-compose -f saiblo-worker-compose.yml up -d
```

## 调试

### 查看日志

```bash
# 查看 Game Host 日志
docker logs <container_id>

# 实时查看日志
docker logs -f <container_id>
```

### 常见问题

1. **连接不上 THUAI8 Server**
   - 检查 Server 是否启动
   - 检查端口是否正确（默认 50051）
   - 检查网络配置

2. **消息格式错误**
   - 检查 JSON 格式是否正确
   - 检查字段名是否匹配

3. **游戏状态不更新**
   - 检查是否正确订阅了 BroadcastGameState
   - 检查是否正确发送了操作

## 待办事项

- [ ] 与后端确认默认棋子配置
- [ ] 与后端确认胜利条件
- [ ] 实现回放文件格式
- [ ] 添加更多错误处理
- [ ] 添加单元测试
- [ ] 优化性能
- [ ] 编写选手 SDK 文档

## 联系方式

如有问题，请联系通信组负责人。
