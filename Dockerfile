# Flask API 的映像
# 建置：docker compose build（不要單獨 docker build，設定都在 docker-compose.yml）
FROM python:3.13.5-slim

WORKDIR /app

# 不產生 .pyc；print / log 立刻輸出，不要被緩衝住（docker logs 才看得到）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 先只複製 requirements.txt 再安裝：程式碼改了但套件沒變時，這層會直接用快取，不用重裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再複製程式碼（哪些檔案不要進映像，看 .dockerignore）
COPY . .

# log 資料夾（compose 會把本機的 ./log 掛在這裡；沒掛時也要存在，gunicorn 才寫得進去）
RUN mkdir -p log

EXPOSE 5000

# 1. 把資料庫升到最新版本（新的空資料庫會從第一支 migration 建出所有表）
# 2. 啟動 gunicorn（設定在 gunicorn.conf.py）
CMD ["sh", "-c", "flask --app main db upgrade && exec gunicorn main:app"]
