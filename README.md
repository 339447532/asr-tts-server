# ASR-TTS 服务器 Docker 部署文档

<div align="center">
  <div>&nbsp;</div>
  <img src="logo.png" width="300"/> 
</div>

## 项目简介

ASR-TTS 服务器是一个集成了自动语音识别(ASR)和文本转语音(TTS)功能的多语言语音处理服务。基于 MeloTTS 高质量多语言文本转语音库构建，支持多种语言的语音合成和识别。

### 支持的语言

| 语言 | 示例 |
| --- | --- |
| English (American)    | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/en/EN-US/speed_1.0/sent_000.wav) |
| English (British)     | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/en/EN-BR/speed_1.0/sent_000.wav) |
| English (Indian)      | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/en/EN_INDIA/speed_1.0/sent_000.wav) |
| English (Australian)  | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/en/EN-AU/speed_1.0/sent_000.wav) |
| English (Default)     | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/en/EN-Default/speed_1.0/sent_000.wav) |
| Spanish               | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/es/ES/speed_1.0/sent_000.wav) |
| French                | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/fr/FR/speed_1.0/sent_000.wav) |
| Chinese (mix EN)      | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/zh/ZH/speed_1.0/sent_000.wav) |
| Japanese              | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/jp/JP/speed_1.0/sent_000.wav) |
| Korean                | [Link](https://myshell-public-repo-host.s3.amazonaws.com/myshellttsbase/examples/kr/KR/speed_1.0/sent_000.wav) |

### 主要特性

- 支持中英文混合语音合成
- CPU 实时推理性能优化
- WebSocket 实时语音识别
- HTTP API 语音合成服务
- 多语言支持
- Docker 容器化部署

## Docker 部署指南

### 系统要求

- Docker Engine 20.10+
- Docker Compose 2.0+ (可选)
- NVIDIA Docker (GPU 支持，推荐)
- 至少 8GB 内存
- 至少 20GB 磁盘空间

### 快速开始

#### 1. 克隆项目

```bash
git clone <repository-url>
cd asr-tts-server-master
```

#### 2. 构建 Docker 镜像

```bash
# 基础构建
docker build -t asr-tts-server:latest .

# 如果需要指定代理（国内用户推荐）
docker build --build-arg https_proxy=http://172.24.222.156:7890 \
             --build-arg http_proxy=http://172.24.222.156:7890 \
             --build-arg all_proxy=socks5://172.24.222.156:7890 \
             -t asr-tts-server:latest .
```

#### 3. 运行容器

```bash
# 基础运行
docker run -d \
  --name asr-tts-server \
  -p 1377:1377 \
  -p 10095:10095 \
  -p 8000:8000 \
  -v $(pwd)/wav_dir:/root/wav_dir \
  asr-tts-server:latest

# GPU 支持运行（推荐）
docker run -d \
  --name asr-tts-server \
  --gpus all \
  -p 1377:1377 \
  -p 10095:10095 \
  -p 8000:8000 \
  -v $(pwd)/wav_dir:/root/wav_dir \
  asr-tts-server:latest
```

### Docker Compose 部署

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  asr-tts-server:
    build: .
    container_name: asr-tts-server
    ports:
      - "1377:1377"   # TTS HTTP API
      - "10095:10095" # ASR WebSocket
      - "8000:8000"   # TTS WebSocket
    volumes:
      - ./wav_dir:/root/wav_dir
      - ./logs:/var/log/supervisor
    environment:
      - CUDA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
```

启动服务：

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 服务端口说明

| 端口 | 服务 | 协议 | 说明 |
|------|------|------|------|
| 1377 | TTS HTTP API | HTTP | 文本转语音 REST API |
| 10095 | ASR WebSocket | WebSocket | 实时语音识别 |
| 8000 | TTS WebSocket | WebSocket | 实时语音合成 |

### 环境配置

#### Dockerfile 配置说明

- **基础镜像**: `nvidia/cuda:11.8.0-base-ubuntu22.04`
- **Python 版本**: 3.10.12 (从源码编译)
- **包管理器**: 使用清华大学镜像源加速
- **进程管理**: Supervisor 管理多个服务进程

#### 关键配置文件

1. **Dockerfile**: 容器构建配置
2. **supervisord.conf**: 进程管理配置
3. **requirements.txt**: Python 依赖包

### API 使用说明

#### TTS HTTP API (端口 1377)

**语音合成接口**
```bash
# GET 请求生成语音文件
curl "http://localhost:1377/speech?text=你好世界&language=ZH&speed=1.0"

# 获取语音文件 URL
curl "http://localhost:1377/speech_url?text=你好世界&language=ZH&speed=1.0"
```

**参数说明**:
- `text`: 要合成的文本
- `language`: 语言代码 (ZH, EN, JP, KR, ES, FR)
- `speed`: 语速 (0.5-2.0)

#### ASR WebSocket (端口 10095)

```javascript
// JavaScript 示例
const websocket = new WebSocket('ws://localhost:10095/ws/upload');

websocket.onopen = () => {
    console.log('WebSocket connection established');
};

websocket.onmessage = (event) => {
    const result = JSON.parse(event.data);
    console.log('识别结果:', result.text);
};

// 发送音频数据
websocket.send(audioBuffer);
```

#### TTS WebSocket (端口 8000)

```javascript
// JavaScript 示例
const websocket = new WebSocket('ws://localhost:8000/');

websocket.onopen = () => {
    // 发送文本合成请求
    websocket.send(JSON.stringify({
        text: "你好世界",
        language: "ZH",
        speed: 1.0
    }));
};

websocket.onmessage = (event) => {
    // 接收音频数据
    const audioData = event.data;
    // 处理音频数据...
};
```

### 故障排除

#### 常见问题

1. **容器启动失败**
   ```bash
   # 查看容器日志
   docker logs asr-tts-server
   
   # 查看详细启动信息
   docker run --rm -it asr-tts-server:latest /bin/bash
   ```

2. **GPU 不可用**
   ```bash
   # 检查 NVIDIA Docker 支持
   docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
   ```

3. **端口冲突**
   ```bash
   # 检查端口占用
   netstat -tulpn | grep -E "(1377|10095|8000)"
   
   # 修改端口映射
   docker run -p 1378:1377 -p 10096:10095 -p 8001:8000 ...
   ```

4. **内存不足**
   ```bash
   # 增加容器内存限制
   docker run --memory=8g --memory-swap=16g ...
   ```

#### 日志查看

```bash
# 查看 supervisor 日志
docker exec -it asr-tts-server tail -f /var/log/supervisor/supervisord.log

# 查看各服务日志
docker exec -it asr-tts-server tail -f /var/log/supervisor/asr_tts.out.log
docker exec -it asr-tts-server tail -f /var/log/supervisor/asr_websocket.out.log
docker exec -it asr-tts-server tail -f /var/log/supervisor/tts_websocket.out.log
```

### 性能优化

#### GPU 优化

```bash
# 指定特定 GPU
docker run --gpus '"device=0"' ...

# 限制 GPU 内存
docker run -e CUDA_VISIBLE_DEVICES=0 -e CUDA_MEM_FRACTION=0.8 ...
```

#### 内存优化

```bash
# 设置内存限制
docker run --memory=8g --memory-swap=16g --oom-kill-disable ...
```

### 开发和调试

#### 开发模式运行

```bash
# 挂载源码目录进行开发
docker run -it --rm \
  -v $(pwd):/root \
  -p 1377:1377 -p 10095:10095 -p 8000:8000 \
  asr-tts-server:latest /bin/bash
```

#### 手动启动服务

```bash
# 进入容器
docker exec -it asr-tts-server /bin/bash

# 手动启动单个服务
cd /root
python3 asr_tts.py
python3 asr_websocket.py --host 0.0.0.0 --port 10095
python3 tts_websocket.py
```
