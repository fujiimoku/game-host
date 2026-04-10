# Game Host Dockerfile
# 需要 .NET 8 Runtime（用于 pythonnet 加载 C# DLL）+ Python 3.11
FROM mcr.microsoft.com/dotnet/runtime:8.0

# 安装 Python 3.11
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 让 python3 指向 3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 复制 Python 代码
COPY saiblo_protocol.py .
COPY game_engine_wrapper.py .
COPY main.py .

# 复制 C# DLL（由后端 publish 产出，没有 DLL 时用 USE_MOCK_DLL=1 运行）
COPY server/ ./server/
# BoardCase 需要在工作目录下（DLL 用相对路径查找）
COPY server/BoardCase/ ./BoardCase/

# 默认使用 Mock，有 DLL 时设置 USE_MOCK_DLL=0
ENV USE_MOCK_DLL=1

CMD ["python3", "-u", "main.py"]
