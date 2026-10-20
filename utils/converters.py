"""
安全的型別轉換

組 API 回應時，資料庫欄位可能是 None 或怪值，
這些函式保證回傳的型別固定（前端 / App 才不會因為 null 當掉）。
"""
from datetime import datetime

from utils.logger import logger


def safe_str(value, default: str = "") -> str:
    """安全轉換為字串（None → default）"""
    return default if value is None else str(value)


def safe_int(value, default: int = 0) -> int:
    """安全轉換為整數（None、空字串、轉不了 → default）"""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    """安全轉換為浮點數，確保回傳數值而非 NaN/Inf"""
    if value is None or value == "":
        return default
    try:
        result = float(value)
        # NaN 不等於自己；Inf 不是有效數值
        if result != result or result == float("inf") or result == float("-inf"):
            return default
        return result
    except (ValueError, TypeError):
        return default


def safe_datetime_str(value, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """安全轉換時間格式，轉不了就回空字串

    - datetime / date → 依 fmt 格式化
    - 字串 → 先試著用常見格式解析再格式化，都解析不了就原樣回傳
    """
    if not value:
        return ""

    try:
        if isinstance(value, str):
            for candidate in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
                try:
                    return datetime.strptime(value, candidate).strftime(fmt)
                except ValueError:
                    continue
            return value

        if hasattr(value, "strftime"):
            return value.strftime(fmt)

    except Exception as e:
        logger.warning(f"時間格式轉換失敗：{e}")

    return ""


def safe_getattr(obj, attr: str, default=""):
    """取屬性，取不到或是空值（None、0、""）都回 default"""
    try:
        return getattr(obj, attr, default) or default
    except Exception:
        return default
