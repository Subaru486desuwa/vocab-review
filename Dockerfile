FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY requirements.lock.txt requirements-dev.lock.txt ./
# 默认安装测试与检查工具；只需运行页面时可用 --build-arg WITH_DEV=0。
ARG WITH_DEV=1
RUN pip install -r requirements.lock.txt \
    && if [ "$WITH_DEV" = "1" ]; then pip install -r requirements-dev.lock.txt; fi

COPY . .

EXPOSE 5000
CMD ["flask", "--app", "app:create_app", "run", "--host", "0.0.0.0", "--port", "5000"]
