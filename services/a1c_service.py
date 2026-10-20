"""
糖化血色素（A1c）與照護記錄

- A1c：a1c_records 表
- 照護：care_records 表（原本誤寫在 a1c_records，改成獨立一張表）

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
from datetime import datetime

from models.user import User
from models.a1c import A1cRecord
from models.care import CareRecord
from utils.api_response import success_body, error_body
from utils.extensions import db
from utils.logger import logger
from utils.time_utils import now_taiwan


class A1cService:

    @staticmethod
    def add_a1c(email: str, a1c_value, record_date: str):
        """新增 A1c 記錄；同一天已經有就更新"""
        try:
            user: User | None = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            if a1c_value <= 3 or a1c_value > 14:
                return error_body("Invalid HbA1c value", "INVALID_HBA1C"), 400

            # 日期由字串轉成 date 物件
            record_date_parsed = datetime.strptime(record_date, "%Y-%m-%d").date()

            existing_record: A1cRecord | None = A1cRecord.query.filter_by(
                user_id=user.id,
                record_date=record_date_parsed,
            ).first()

            if existing_record:
                existing_record.a1cs = a1c_value
                existing_record.updated_at = now_taiwan()
            else:
                db.session.add(A1cRecord(
                    user_id=user.id,
                    a1cs=a1c_value,
                    record_date=record_date_parsed,
                ))

            db.session.commit()
            return success_body(), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增 A1c 記錄失敗：{e}")
            return error_body("Failed to add HbA1c record", "ADD_HBA1C_FAILED"), 500

    @staticmethod
    def get_a1c_records(email: str):
        """取得所有 A1c 記錄，日期新的在前"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            a1c_records = (
                A1cRecord.query
                .filter_by(user_id=user.id)
                .order_by(A1cRecord.record_date.desc())
                .all()
            )

            records_list = []
            for record in a1c_records:
                records_list.append({
                    "id": record.id,
                    "user_id": record.user_id,
                    "a1cs": str(record.a1cs),
                    "record_date": record.record_date.strftime("%Y-%m-%d"),
                    "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                })

            return success_body(a1cs=records_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得 A1c 記錄失敗：{e}")
            return error_body("Failed to get HbA1c records", "GET_HBA1C_FAILED"), 500

    @staticmethod
    def add_care_record(email: str, care_data: str):
        """新增照護記錄；同樣內容已經有就只更新時間"""
        try:
            user: User | None = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            if not isinstance(care_data, str) or not care_data.strip():
                return error_body("Care data cannot be empty", "CARE_DATA_REQUIRED"), 400

            existing_record: CareRecord | None = CareRecord.query.filter_by(
                user_id=user.id,
                care_data=care_data.strip(),
            ).first()

            if existing_record:
                existing_record.updated_at = now_taiwan()
            else:
                db.session.add(CareRecord(
                    user_id=user.id,
                    care_data=care_data.strip(),
                ))
            db.session.commit()

            return success_body(), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增照護記錄失敗：{e}")
            return error_body("Failed to add care record", "ADD_CARE_FAILED"), 500

    @staticmethod
    def get_care_records(email: str):
        """取得所有照護記錄，新的在前"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            # created_at 只到秒，同一秒的用 id 排
            care_records = (
                CareRecord.query
                .filter_by(user_id=user.id)
                .order_by(CareRecord.created_at.desc(), CareRecord.id.desc())
                .all()
            )

            records_list = []
            for record in care_records:
                records_list.append({
                    "id": record.id,
                    "user_id": record.user_id,
                    "cares": record.care_data,
                    "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                })

            return success_body(cares=records_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得照護記錄失敗：{e}")
            return error_body("Failed to get care records", "GET_CARE_FAILED"), 500
