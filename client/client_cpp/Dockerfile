FROM gcc:13

# 安装 cmake 和 json 解析库
RUN apt-get update && apt-get install -y \
    cmake \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 编译 C++ 客户端
RUN mkdir build && cd build && \
    cmake .. && \
    make

CMD ["./build/thuai9_client"]