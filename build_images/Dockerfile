# 多阶段构建：从预构建镜像中获取模型文件
# 支持通过 BUILD_PLATFORM 参数指定平台 (linux/mac/win)，默认为 linux
ARG BUILD_PLATFORM=linux
ARG MODEL_VERSION=v1.5.1
FROM xixihahaliu01/qanything-${BUILD_PLATFORM}:${MODEL_VERSION} as models-source

# 第二阶段：构建运行环境
FROM python:3.10.14-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    vim \
    wget \
    htop \
    build-essential \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 创建TikToken缓存目录
RUN mkdir /opt/tiktoken_cache

# 下载TikToken模型缓存
ARG TIKTOKEN_URL="https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
RUN wget -O /opt/tiktoken_cache/$(echo -n $TIKTOKEN_URL | sha1sum | head -c 40) "$TIKTOKEN_URL"

# 设置环境变量指向TikToken缓存目录
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken_cache

# 复制 requirements.txt 文件到容器中
COPY requirements.txt /tmp/requirements.txt

# 安装 Python 依赖
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 从预构建镜像复制模型文件（多阶段构建）
# 如果本地有 models 目录，优先使用本地（用于离线构建）
COPY --from=models-source /root/models /root/models
COPY --from=models-source /root/nltk_data /root/nltk_data

# 如果本地有 models 目录，可以取消注释下面两行，使用本地模型（覆盖从镜像复制的）
# COPY models /root/models
# COPY nltk_data /root/nltk_data

# 设置工作目录
WORKDIR /workspace

# 清理 APT 缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# 验证模型文件是否存在
RUN if [ ! -d "/root/models" ]; then \
        echo "错误: /root/models 目录不存在"; \
        exit 1; \
    elif [ ! -d "/root/models/linux_onnx" ] && [ ! -d "/root/models/mac_onnx" ] && [ ! -d "/root/models/win_onnx" ]; then \
        echo "警告: 未找到模型子目录 (linux_onnx/mac_onnx/win_onnx)"; \
        echo "模型目录内容:"; \
        ls -la /root/models/ || true; \
    else \
        echo "✅ 模型文件验证成功"; \
        echo "模型目录结构:"; \
        ls -la /root/models/ | head -10; \
    fi

# 设置默认命令
CMD ["/bin/bash"]

