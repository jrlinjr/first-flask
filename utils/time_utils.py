"""時間相關的共用工具"""
from datetime import datetime, timedelta, timezone

# 台灣時區（UTC+8）
TZ_TAIWAN = timezone(timedelta(hours=8))

# 前端傳記錄時間用的格式
RECORDED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_taiwan() -> datetime:
    """現在時間（帶台灣時區）"""
    return datetime.now(TZ_TAIWAN)


def parse_recorded_at(recorded_at: str) -> datetime:
    """把 "YYYY-MM-DD HH:MM:SS" 轉成帶台灣時區的 datetime

    格式不對會丟 ValueError，由呼叫端決定要回錯誤還是改用現在時間。
    """
    recorded_datetime = datetime.strptime(recorded_at, RECORDED_AT_FORMAT)
    return recorded_datetime.replace(tzinfo=TZ_TAIWAN)
