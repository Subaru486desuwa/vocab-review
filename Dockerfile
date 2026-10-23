FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY requirements.lock.txt requirements-dev.lock.txt requirements-ml.lock.txt ./
# 默认安装测试工具与实验三依赖；--build-arg WITH_DEV=0 / WITH_ML=0 可省略，不含模型依赖时基础页面与学习流程照常运行。
ARG WITH_DEV=1
ARG WITH_ML=1
RUN pip install -r requirements.lock.txt \
    && if [ "$WITH_DEV" = "1" ]; then pip install -r requirements-dev.lock.txt; fi \
    && if [ "$WITH_ML" = "1" ]; then pip install -r requirements-ml.lock.txt; fi

COPY . .

EXPOSE 5000
CMD ["flask", "--app", "app:create_app", "run", "--host", "0.0.0.0", "--port", "5000"]
