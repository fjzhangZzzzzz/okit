FROM python:3.11-slim AS base

# 安装 uv
RUN pip install --no-cache-dir uv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /root/.cache /okit/tests /okit/.git

# 拷贝项目代码
COPY . /okit
WORKDIR /okit

# 安装 okit 及依赖到系统环境
RUN uv pip install . --system --no-cache-dir

ENTRYPOINT ["okit"]
CMD ["--help"] 