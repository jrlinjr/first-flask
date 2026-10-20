# 把所有 model 都 import 進來，確保 SQLAlchemy 認得每一張表
# （ShareRecord 用字串 "Diary" 建關聯，Diary 一定要先被載入）
from .user import User
from .user_default import UserDefault
from .user_setting import UserSetting
from .user_vip import UserVip
from .user_medical import medical_records
from .a1c import A1cRecord
from .care import CareRecord
from .diary import Diary
from .friend import Friend
from .friendresult import FriendResult
from .news import News
from .share import ShareRecord

__all__ = [
    "User", "UserDefault", "UserSetting", "UserVip", "medical_records",
    "A1cRecord", "CareRecord", "Diary", "Friend", "FriendResult", "News", "ShareRecord",
]
