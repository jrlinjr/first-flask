"""輸入格式檢查"""
import re

# Email 格式：有 @、@ 後面有 .、中間沒有空白
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))
