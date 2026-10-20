"""
集中管理環境變數

其他檔案一律用 `from shared import env` 取設定，不要各自 os.getenv()，
這樣要查「有哪些設定」只要看這一個檔。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 不管從哪個資料夾啟動，都讀專案根目錄的 .env
# 已經存在的環境變數不會被 .env 蓋掉（測試就是靠這點改連 first_test）
load_dotenv(Path(__file__).resolve().parent / ".env")


class Env:
    """基礎設定（來自環境變數 / .env）"""

    def __init__(self):
        # 資料庫
        self.database_uri: str | None = os.getenv("SQLALCHEMY_DATABASE_URI")

        # JWT
        self.jwt_secret_key: str | None = os.getenv("JWT_SECRET_KEY")

        # 郵件（Gmail SMTP）
        self.mail_server: str | None = os.getenv("MAIL_SERVER")
        self.mail_port: int = int(os.getenv("MAIL_PORT", 587))
        self.mail_use_tls: bool = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
        self.mail_username: str | None = os.getenv("MAIL_USERNAME")
        self.mail_password: str | None = os.getenv("MAIL_PASSWORD")
        # 設成 1 就不真的寄信（只寫 log），開發 / 測試時避免一直寄信
        self.mail_suppress_send: bool = os.getenv("MAIL_SUPPRESS_SEND", "0") == "1"

        # 開發伺服器的埠號（macOS 的 AirPlay 接收器會佔用 5000，撞到時改成別的）
        self.port: int = int(os.getenv("PORT", 5000))

        # log：設成 1 時，每個等級各寫一個檔到 log/（debug.log、info.log、warning.log、error.log、critical.log）
        self.log_to_file: bool = os.getenv("LOG_TO_FILE", "1") == "1"


env = Env()
__all__ = ["env"]
