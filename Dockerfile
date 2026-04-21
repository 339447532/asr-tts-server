ARG BASE=nvidia/cuda:11.8.0-base-ubuntu22.04
FROM ${BASE}

# 设置时区为东8区（Asia/Shanghai）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 配置DNS解析 - 使用更安全的方式
RUN mkdir -p /etc/systemd/resolved.conf.d/ && \
    echo "[Resolve]" > /etc/systemd/resolved.conf.d/dns.conf && \
    echo "DNS=8.8.8.8 114.114.114.114" >> /etc/systemd/resolved.conf.d/dns.conf

# 配置清华源并安装必要的系统依赖和Python 3.10.12
RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list && \
    sed -i 's@//.*security.ubuntu.com@//mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list && \
    apt-get update && apt-get upgrade -y
RUN apt-get install -y --no-install-recommends \
    gcc g++ make \
    software-properties-common \
    wget \
    curl \
    git \
    net-tools \
    iputils-ping \
    dnsutils \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    espeak-ng \
    libsndfile1-dev \
    supervisor \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*


# 从华为镜像站安装Python 3.10.12
RUN wget https://mirrors.huaweicloud.com/python/3.10.12/Python-3.10.12.tgz && \
    tar xzf Python-3.10.12.tgz && \
    cd Python-3.10.12 && \
    ./configure --enable-optimizations && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.10.12* && \
    ln -sf /usr/local/bin/python3.10 /usr/bin/python3 && \
    ln -sf /usr/local/bin/pip3.10 /usr/bin/pip3


# Clone TTS repository contents from GitLab:
RUN rm -rf /root/* /root/.* 2>/dev/null || true
WORKDIR /root
RUN git clone https://github.com/339447532/asr-tts-server.git .

# 使用pip安装项目依赖
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip3 install llvmlite --ignore-installed
# 更新pip到最新版本
RUN pip3 install --upgrade pip
# 安装Python依赖
RUN pip3 install -r requirements.txt

# 在容器启动时重新拉取代码并安装依赖，再启动服务
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# 安装supervisor的Python包
RUN pip3 install supervisor

# 设置 PIP_MAX_ROUNDS 环境变量和代理
ENV PIP_MAX_ROUNDS=400000
ENV https_proxy=http://172.24.219.25:7890
ENV http_proxy=http://172.24.219.25:7890
ENV all_proxy=socks5://172.24.219.25:7890

# 创建supervisor配置文件
RUN mkdir -p /etc/supervisor/conf.d
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 暴露端口
EXPOSE 1377 10095 8000

# 使用supervisor启动多个服务
CMD ["python3", "-m", "supervisor.supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
