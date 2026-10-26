FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# GDAL/GEOS 是 django.contrib.gis + PostGIS 后端的硬依赖，但 pip 装不了 ——
# 必须用系统包。原版只在 Dockerfile 里补了，requirements.txt 一字没提，
# 于是任何非 Docker 部署（离线环境常见）都会在 import 阶段失败。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev gcc libgdal-dev gdal-bin libgeos-dev \
        postgresql-client python3-gdal \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
# 原版是 `manage.py runserver`。那是开发服务器：单进程、无并发处理、
# 官方文档明确禁止用于生产。gunicorn 本来就在 requirements 里装着。
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]