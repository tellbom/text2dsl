FROM python:3.10

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 更新系统包管理器并安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    vim \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 更换阿里镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple
# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖包，包含所有可能需要的包
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]