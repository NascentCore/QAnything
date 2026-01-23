# Docker 镜像构建说明

## 多阶段构建

Dockerfile 使用多阶段构建，自动从预构建镜像中提取模型文件，无需手动下载。

## 构建命令

### Linux 平台（默认）

```bash
docker build -f build_images/Dockerfile -t qanything:latest .
```

### Mac 平台

```bash
docker build -f build_images/Dockerfile \
  --build-arg BUILD_PLATFORM=mac \
  -t qanything:latest .
```

### Windows 平台

```bash
docker build -f build_images/Dockerfile \
  --build-arg BUILD_PLATFORM=win \
  -t qanything:latest .
```

### 指定模型版本

```bash
docker build -f build_images/Dockerfile \
  --build-arg BUILD_PLATFORM=linux \
  --build-arg MODEL_VERSION=v1.5.1 \
  -t qanything:latest .
```

## 工作原理

1. **第一阶段（models-source）**：从预构建镜像 `xixihahaliu01/qanything-{platform}:{version}` 中获取模型文件
2. **第二阶段（主镜像）**：
   - 基于 Python 3.10.14-slim
   - 安装系统依赖和 Python 包
   - 从第一阶段复制模型文件到 `/root/models` 和 `/root/nltk_data`

## 离线构建

如果需要离线构建，可以先下载模型到本地：

```bash
# 使用下载脚本
./scripts/download_models.sh linux

# 然后修改 Dockerfile，取消注释本地复制部分：
# COPY models /root/models
# COPY nltk_data /root/nltk_data
```

## 验证

构建完成后，可以验证模型文件：

```bash
docker run --rm qanything:latest ls -la /root/models/
```

## 注意事项

- 首次构建需要拉取预构建镜像，可能需要较长时间
- 确保有足够的磁盘空间（模型文件约 4-5GB）
- 如果网络不稳定，可以先手动拉取镜像：`docker pull xixihahaliu01/qanything-linux:v1.5.1`
