"""
彩色 log

用法：
    from utils.logger import logger
    logger.info("訊息")
    logger.error("錯誤")

- 終端機：依等級上色（DEBUG 紫、INFO 綠、WARNING 黃、ERROR 紅）
- LOG_TO_FILE=1（預設）時，每個等級各寫一個檔（每個檔只收自己那個等級）：
    log/debug.log  log/info.log  log/warning.log  log/error.log  log/critical.log
  每個檔滿 10 MB 就換新檔，最多留 5 份舊的（例如 error.log.1 ~ error.log.5）
  要看完整時間順序：sort -m log/*.log
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from shared import env

LOG_FORMAT = "%(asctime)s %(levelname)s:%(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 各等級對應的 ANSI 顏色碼
LEVEL_COLORS = {
    logging.DEBUG: "\x1b[35m",
    logging.INFO: "\x1b[32m",
    logging.WARNING: "\x1b[33m",
    logging.ERROR: "\x1b[31m",
    logging.CRITICAL: "\x1b[31m",
}
RESET_COLOR = "\x1b[0m"

LOG_DIR = Path(__file__).resolve().parent.parent / "log"

# 等級 → 檔名
LEVEL_FILES = {
    logging.DEBUG: "debug.log",
    logging.INFO: "info.log",
    logging.WARNING: "warning.log",
    logging.ERROR: "error.log",
    logging.CRITICAL: "critical.log",
}
MAX_BYTES = 10 * 1024 * 1024  # 單檔 10 MB
BACKUP_COUNT = 5              # 最多留 5 份舊檔


class LevelFilter(logging.Filter):
    """讓 handler 只接收某一個等級的 log"""

    def __init__(self, level: int):
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self.level


class ColorFormatter(logging.Formatter):
    """在終端機輸出時，把整行訊息依等級上色"""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        color = LEVEL_COLORS.get(record.levelno, "")
        return f"{color}{text}{RESET_COLOR}"


logger = logging.getLogger("first_api")
logger.setLevel(logging.DEBUG)
# 不往 root logger 傳，避免同一行印兩次
logger.propagate = False

# 避免模組被重複 import 時重複加 handler
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    if env.log_to_file:
        LOG_DIR.mkdir(exist_ok=True)
        for level, filename in LEVEL_FILES.items():
            file_handler = RotatingFileHandler(
                LOG_DIR / filename,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.addFilter(LevelFilter(level))
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
            logger.addHandler(file_handler)
