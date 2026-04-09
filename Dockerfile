# 使用 .NET 8.0 运行时作为基础镜像
FROM mcr.microsoft.com/dotnet/runtime:8.0

# 安装 Python 3 和构建依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装
COPY requirements.txt .
# Debian 系统下需要加 --break-system-packages 允许全局安装
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 复制 C# 编译好的 DLL 文件到容器中
# 对应测试文档中的 cp -r bin/Debug/net8.0/. ../../../game-host/server/
COPY server/ ./server/

# 复制 Python 主机的所有代码
COPY . .

# 默认环境变量：使用真实的 DLL（可以在 docker run 时被覆盖）
ENV USE_MOCK_DLL=0

# -u 参数保证 Python 实时输出不缓冲，防止通信死锁
CMD ["python3", "-u", "main.py"]