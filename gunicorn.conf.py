"""
gunicorn 設定（Docker 裡用；gunicorn 啟動時會自動讀目前資料夾的 gunicorn.conf.py）

本機開發還是用 python main.py，不會用到這支。
"""

bind = "0.0.0.0:5000"

# 1 個 process + 4 個 thread
# 只有一個 process 在寫 log 檔，「滿了自動換檔」才不會因為多個 process 同時寫而出錯
workers = 1
threads = 4

# gunicorn 的 log（有設 logconfig_dict，gunicorn 就照這裡輸出，不用另外設 accesslog）：
# - 請求記錄（access log）→ log/access.log
# - gunicorn 自己的訊息（啟動、worker 重開…）→ log/gunicorn.log
#   （這些是 master process 寫的，跟 app 的 log/info.log 等分開，兩個 process 才不會同時寫同一個檔）
# 兩種都會同時印在 docker compose logs
ROTATE = {"maxBytes": 10 * 1024 * 1024, "backupCount": 5, "encoding": "utf-8"}  # 滿 10 MB 換檔，留 5 份

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # access log 的內容 gunicorn 已經排好格式，直接輸出
        "plain": {"format": "%(message)s"},
        "console": {
            "format": "%(asctime)s [%(process)d] %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "stream": "ext://sys.stdout",
        },
        "access_console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stdout",
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "log/access.log",
            "formatter": "plain",
            **ROTATE,
        },
        "gunicorn_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "log/gunicorn.log",
            "formatter": "console",
            **ROTATE,
        },
    },
    "loggers": {
        "gunicorn.error": {"level": "INFO", "handlers": ["gunicorn_file", "console"], "propagate": False},
        "gunicorn.access": {"level": "INFO", "handlers": ["access_file", "access_console"], "propagate": False},
    },
}
