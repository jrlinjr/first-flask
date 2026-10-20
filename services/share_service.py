"""
分享健康記錄給好友

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
from sqlalchemy.orm import joinedload

from models.user import User
from models.share import ShareRecord
from models.friendresult import FriendResult
from utils.api_response import success_body, error_body
from utils.extensions import db
from utils.logger import logger
from utils.time_utils import now_taiwan

# record_type：0 血壓、1 體重、2 血糖、3 飲食
VALID_RECORD_TYPES = [0, 1, 2, 3]

# 一次最多回傳幾筆分享
SHARED_RECORDS_LIMIT = 50

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_time(value) -> str:
    if value:
        return value.strftime(DATETIME_FORMAT)
    return ""


class ShareService:

    @staticmethod
    def add_share_record(email: str, record_type: int, record_id: int, relation_type: int):
        """分享一筆記錄給某個分組；同一筆分享過就更新分享時間"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            if record_type not in VALID_RECORD_TYPES:
                return error_body("Invalid type parameter", "INVALID_TYPE"), 400

            if not record_id or record_id <= 0:
                return error_body("Invalid record_id parameter", "INVALID_RECORD_ID"), 400

            existing_share = ShareRecord.query.filter_by(
                user_id=user.id,
                record_type=record_type,
                record_id=record_id,
                relation_type=relation_type,
            ).first()

            if existing_share:
                existing_share.shared_at = now_taiwan()
                existing_share.updated_at = now_taiwan()
                db.session.commit()
                return success_body("Update share successful", "UPDATE_SHARE_SUCCESS"), 200

            db.session.add(ShareRecord(
                user_id=user.id,
                record_type=record_type,
                record_id=record_id,
                relation_type=relation_type,
                shared_at=now_taiwan(),
                created_at=now_taiwan(),
                updated_at=now_taiwan(),
            ))
            db.session.commit()
            return success_body("Share successful", "SHARE_SUCCESS"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 分享記錄失敗：{e}")
            return error_body("Share failed", "SHARE_FAILED"), 500

    @staticmethod
    def get_shared_records(email: str, relation_type):
        """
        好友分享給我的健康記錄

        Args:
            relation_type: 0 醫師團、1 親友團、2 控糖團
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            # 我送出且已接受的
            my_friends_sent = FriendResult.query.filter_by(user_id=user.id, type=relation_type, status=1).all()
            # 我收到且已接受的
            my_friends_received = FriendResult.query.filter_by(relation_id=user.id, type=relation_type, status=1).all()

            # 收集所有好友的 user_id
            friend_ids = set()
            for relation in my_friends_sent:
                friend_ids.add(relation.relation_id)
            for relation in my_friends_received:
                friend_ids.add(relation.user_id)

            if not friend_ids:
                return success_body(records=[]), 200

            share_records = (
                ShareRecord.query
                .options(joinedload(ShareRecord.user))  # 預先載入分享者資訊
                .filter(
                    ShareRecord.user_id.in_(friend_ids),
                    ShareRecord.relation_type == relation_type,
                )
                .order_by(ShareRecord.created_at.desc())
                .limit(SHARED_RECORDS_LIMIT)
                .all()
            )

            records_list = []
            for share in share_records:
                sharer = share.user
                if not sharer:
                    continue

                diary = share.diary
                if not diary:
                    continue

                records_list.append({
                    "id": share.id,
                    "user_id": share.user_id,
                    "relation_id": getattr(share, "relation_id", 0),
                    "user": {
                        "id": sharer.id,
                        "name": sharer.name or "",
                        "email": sharer.email or "",
                        "account": sharer.account or "",
                    },
                    "type": share.record_type,
                    "record_type": share.record_type,
                    "weight": float(diary.weight or 0),
                    "body_fat": float(diary.body_fat or 0),
                    "sugar": float(diary.sugar or 0),
                    "meal_type": int(diary.meal or 0),
                    "bmi": float(diary.bmi or 0),
                    "shared_at": _format_time(share.shared_at),
                    "recorded_at": _format_time(diary.recorded_at),
                    "created_at": _format_time(diary.created_at),
                    "meal": int(diary.meal or 0),
                    "timeperiod": int(diary.timeperiod or 0),
                    "tag": [[]],
                    "image": [],
                    "location": {"lat": "", "lng": "", "address": ""},
                    "relation_type": share.relation_type,
                    "systolic": int(diary.systolic or 0),
                    "diastolic": int(diary.diastolic or 0),
                    "pulse": int(diary.pulse or 0),
                    "message": str(diary.description or ""),
                    "url": "",
                    "record_status": 0,
                })

            return success_body(records=records_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得分享記錄失敗：{e}")
            return error_body("Failed to get share records", "GET_SHARE_RECORDS_FAILED"), 500
