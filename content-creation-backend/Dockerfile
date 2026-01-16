# 后端Docker镜像构建文件
# 多阶段构建，优化镜像大小

# 阶段1: 基础Python环境
FROM python:3.11-slim as base

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    ffmpeg \
    fontconfig \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 构建字体缓存，确保 FFmpeg/libass 可找到中文字体（避免字幕“方块/乱码”）
RUN fc-cache -f -v

# 设置工作目录
WORKDIR /app

# 阶段2: 依赖安装
FROM base as dependencies

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 阶段3: 应用构建
FROM base as application

# 从依赖阶段复制安装的包
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建非root用户运行应用
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--forwarded-allow-ips", "*"]

