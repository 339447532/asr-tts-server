#!/bin/sh
set -e

# 在容器启动时执行：拉最新代码、安装依赖，然后启动原 CMD
cd /root || exit 1

if [ -d .git ]; then
  echo "[entrypoint] Pulling latest git code..."
  # 尝试拉取最新代码，失败不阻塞后续（例如非快进更新）
  if ! git pull --rebase --autostash; then
    echo "[entrypoint] git pull failed, trying fetch & reset to remote HEAD"
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    git fetch --all || true
    git reset --hard "origin/${BRANCH}" || true
  fi
else
  echo "[entrypoint] Repo not found, cloning..."
  git clone "http://root:KAAfVK%23%40h%40xNv@172.24.222.16:2080/AI/asr-tts-server.git" .
fi

echo "[entrypoint] Installing Python dependencies..."
pip3 install --no-cache-dir -r requirements.txt

#本地运行时，需要下载模型
#huggingface-cli download --resume-download hexgrad/Kokoro-82M-v1.1-zh --local-dir ./ckpts/kokoro-v1.1

# docker 运行时，需要下载模型到 /root/ckpts/kokoro-v1.1
huggingface-cli download --resume-download hexgrad/Kokoro-82M-v1.1-zh --local-dir /root/ckpts/kokoro-v1.1

echo "[entrypoint] Starting application..."
exec "$@"

