ARG PYTHON_BASE_IMAGE=python:3.11-slim-bookworm
FROM ${PYTHON_BASE_IMAGE}

ARG APT_MIRROR=http://mirrors.aliyun.com/debian
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST}

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|http://deb.debian.org/debian-security|${APT_MIRROR}-security|g; s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i "s|http://deb.debian.org/debian-security|${APT_MIRROR}-security|g; s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list; \
    fi; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends curl gcc libffi-dev; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --index-url "${PIP_INDEX_URL}" --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

RUN mkdir -p /app/data

CMD ["scrapy", "list"]
