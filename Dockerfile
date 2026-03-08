FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 proto 生成的代码
COPY message_pb2.py .
COPY message_pb2_grpc.py .

# 复制主程序
COPY saiblo_protocol.py .
COPY thuai8_client.py .
COPY main.py .

# 复制 THUAI8 Server（如果需要在容器内运行）
# COPY server/ ./server/

# 运行
CMD ["python", "-u", "main.py"]
