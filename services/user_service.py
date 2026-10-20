"""
使用者：個人資料、通知設定、病歷、徽章

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
from models.user import User
from models.a1c import A1cRecord
from models.user_vip import UserVip
from models.user_default import UserDefault
from models.user_setting import UserSetting
from models.user_medical import medical_records
from utils.api_response import success_body, error_body
from utils.code_generator import generate_invite_code
from utils.converters import safe_str, safe_int, safe_float, safe_datetime_str, safe_getattr
from utils.extensions import db
from utils.logger import logger
from utils.time_utils import now_taiwan

# 糖尿病類型：資料庫存中文，API 用數字
DIABETES_TYPE_NAMES = {
    0: "無",
    1: "糖尿病前期",
    2: "第一型",
    3: "第二型",
    4: "妊娠",
}

# 可以更新的通知 / 單位設定（值一律轉成 0 或 1）
SETTING_FIELDS = {
    "after_recording": "記錄後通知",
    "no_recording_for_a_day": "一天未記錄通知",
    "over_max_or_under_min": "超過最大 / 最小值通知",
    "after_meal": "飯後通知",
    "unit_of_sugar": "血糖單位",
    "unit_of_weight": "體重單位",
    "unit_of_height": "身高單位",
}

# user_defaults 表裡的上下限欄位
DEFAULT_FLOAT_FIELDS = [
    "sugar_delta_max", "sugar_delta_min",
    "sugar_morning_max", "sugar_morning_min",
    "sugar_evening_max", "sugar_evening_min",
    "sugar_before_max", "sugar_before_min",
    "sugar_after_max", "sugar_after_min",
]
DEFAULT_INT_FIELDS = [
    "systolic_max", "systolic_min",
    "diastolic_max", "diastolic_min",
    "pulse_max", "pulse_min",
]
DEFAULT_BODY_FLOAT_FIELDS = [
    "weight_max", "weight_min",
    "bmi_max", "bmi_min",
    "body_fat_max", "body_fat_min",
]


class UserService:

    @staticmethod
    def get_user(email: str):
        """取得使用者完整資訊（含 default / setting / vip / a1c）

        子資料可能還不存在（None），getattr(None, 欄位, 預設值) 會直接回預設值，
        所以下面不用一個一個判斷 None。
        """
        try:
            # 1. 查詢主用戶資料
            user = User.query.filter_by(email=email).first()
            if not user:
                logger.warning(f"[帳號:{email}] 找不到使用者")
                return error_body("User not found", "USER_NOT_FOUND"), 400
            user_id = user.id

            # 2. 查詢相關資料
            user_default: UserDefault | None = UserDefault.query.filter_by(user_id=user_id).first()
            user_setting: UserSetting | None = UserSetting.query.filter_by(user_id=user_id).first()
            user_vip: UserVip | None = UserVip.query.filter_by(user_id=user_id).first()
            user_a1c: A1cRecord | None = (
                A1cRecord.query
                .filter_by(user_id=user_id)
                .order_by(A1cRecord.created_at.desc())
                .first()
            )

            # 3. 處理基本用戶資料
            invite_code = safe_str(getattr(user, "invite_code", None)) or generate_invite_code(user_id)
            vip_level = safe_int(getattr(user_vip, "level", 0))

            user_data = {
                "id": safe_int(user_id),
                "name": safe_str(getattr(user, "name", "")),
                "account": safe_str(getattr(user, "account", "")),
                "email": safe_str(getattr(user, "email", "")),
                "phone": safe_str(getattr(user, "phone", "")),
                "fb_id": safe_str(getattr(user, "fb_id", "")),
                "status": "VIP" if vip_level > 0 else "general",
                "group": safe_str(getattr(user, "group", "0")),
                "birthday": safe_datetime_str(getattr(user, "birthday", None), "%Y-%m-%d"),
                "height": safe_float(getattr(user, "height", 0.0)),
                "weight": safe_float(getattr(user, "weight", 0.0)),
                "gender": 1 if getattr(user, "gender", False) else 0,
                "address": safe_str(getattr(user, "address", "")),
                "unread_records": [0, 0, 0],
                "verified": 1 if getattr(user, "is_verified", False) else 0,
                "privacy_policy": 1,
                "must_change_password": safe_int(getattr(user, "must_change_password", 0)),
                "fcm_id": safe_str(getattr(user, "fcm_id", "")),
                "login_times": safe_int(getattr(user, "login_times", 0)),
                "created_at": safe_datetime_str(getattr(user, "created_at", None)),
                # users 表沒有 updated_at，沿用 created_at
                "updated_at": safe_datetime_str(getattr(user, "created_at", None)),
                "invite_code": invite_code,
                # 不回傳 verification_code：驗證碼只能從信箱拿到，回傳出去等於可以繞過 email 驗證
            }

            # 4. 各項上下限設定
            default_data = {
                "id": safe_int(getattr(user_default, "id", 0)),
                "user_id": safe_int(user_id),
                "created_at": safe_datetime_str(getattr(user_default, "created_at", None)),
                "updated_at": safe_datetime_str(getattr(user_default, "updated_at", None)),
            }
            for field in DEFAULT_FLOAT_FIELDS + DEFAULT_BODY_FLOAT_FIELDS:
                default_data[field] = safe_float(getattr(user_default, field, 0.0))
            for field in DEFAULT_INT_FIELDS:
                default_data[field] = safe_int(getattr(user_default, field, 0))

            # 5. 通知 / 單位設定
            setting_data = {
                "id": safe_int(getattr(user_setting, "id", 0)),
                "user_id": safe_int(user_id),
                "created_at": safe_datetime_str(getattr(user_setting, "created_at", None)),
                "updated_at": safe_datetime_str(getattr(user_setting, "updated_at", None)),
            }
            for field in SETTING_FIELDS:
                setting_data[field] = safe_int(getattr(user_setting, field, 0))

            # 6. VIP
            vip_data = {
                "id": safe_int(getattr(user_vip, "id", 0)),
                "user_id": safe_int(user_id),
                "level": vip_level,
                "remark": safe_float(getattr(user_vip, "remark", 0.0)),  # 必須是 Double
                "started_at": safe_datetime_str(getattr(user_vip, "started_at", None)),
                "ended_at": safe_datetime_str(getattr(user_vip, "ended_at", None)),
                "created_at": safe_datetime_str(getattr(user_vip, "created_at", None)),
                "updated_at": safe_datetime_str(getattr(user_vip, "updated_at", None)),
            }

            # 7. 最新一筆 A1c（model 欄位叫 a1cs / Message）
            a1c_data = {
                "message": safe_str(getattr(user_a1c, "Message", "")),
                "latest_value": safe_float(getattr(user_a1c, "a1cs", 0.0)),
                "latest_date": safe_datetime_str(getattr(user_a1c, "record_date", None)),
            }

            # 8. 組裝最終回應（default、setting、vip、a1c 放在 user 裡面）
            user_data["default"] = default_data
            user_data["setting"] = setting_data
            user_data["vip"] = vip_data
            user_data["a1c"] = a1c_data
            return success_body("success", "SUCCESS", user=user_data), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得使用者資料失敗：{e}")
            return error_body("Failed to get user information", "GET_USER_FAILED"), 500

    @staticmethod
    def update_user(email: str, user_data: dict):
        """更新使用者資料（只更新有傳的欄位）"""
        logger.info(f"[帳號:{email}] 更新使用者資料")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            # 記錄更新前的 email（備份，最後確保不會被改成空的）
            original_email = user.email

            if "name" in user_data:
                user.name = user_data.get("name")

            if "birthday" in user_data:
                user.birthday = user_data.get("birthday")

            # 身高：0 或 None 不更新
            if "height" in user_data:
                height_value = user_data.get("height")
                if height_value is not None and height_value != 0:
                    user.height = height_value

            # 體重：只處理非空值，轉不成數字就略過
            if "weight" in user_data:
                weight_value = user_data.get("weight")
                if weight_value and weight_value != "":
                    try:
                        user.weight = float(weight_value)
                    except (ValueError, TypeError):
                        pass

            if "phone" in user_data:
                user.phone = user_data.get("phone")

            # Email：空的直接忽略；換成別人用過的回錯誤
            if "email" in user_data:
                new_email = user_data.get("email")
                if new_email and new_email.strip():
                    new_email = new_email.strip()
                    if new_email != user.email:
                        if User.query.filter_by(email=new_email).first():
                            return error_body("This email is already in use", "EMAIL_ALREADY_USED"), 400
                        user.email = new_email

            # 性別：None 不更新
            if "gender" in user_data:
                gender_value = user_data.get("gender")
                if gender_value is not None:
                    user.gender = bool(gender_value)

            # FCM ID（推播用）：空值不更新
            if "fcm_id" in user_data:
                fcm_id = user_data.get("fcm_id")
                if fcm_id:
                    user.fcm_id = fcm_id

            if "group" in user_data:
                user.group = user_data.get("group")

            if "fb_id" in user_data:
                user.fb_id = user_data.get("fb_id")

            if "address" in user_data:
                user.address = user_data.get("address")

            # Account：空的忽略；換成別人用過的回錯誤
            if "account" in user_data:
                new_account = user_data.get("account")
                if new_account and new_account.strip():
                    new_account = new_account.strip()
                    if new_account != user.account:
                        if User.query.filter_by(account=new_account).first():
                            return error_body("This account is already in use", "ACCOUNT_ALREADY_USED"), 409
                        user.account = new_account

            # 最終安全檢查 - 確保 email 絕對不會是空的
            if not user.email or user.email.strip() == "":
                user.email = original_email

            db.session.commit()
            return success_body(), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 更新使用者資料失敗：{e}")
            return error_body("Update failed", "UPDATE_FAILED"), 500

    @staticmethod
    def update_user_setting(email: str, setting_data: dict):
        """更新通知 / 單位設定，沒有設定記錄就新建一筆"""
        logger.info(f"[帳號:{email}] 更新使用者設定")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            user_setting = UserSetting.query.filter_by(user_id=user.id).first()
            if not user_setting:
                user_setting = UserSetting(user_id=user.id)
                db.session.add(user_setting)

            # 有傳的欄位才更新，值轉成 0 或 1
            for field in SETTING_FIELDS:
                if field in setting_data:
                    setattr(user_setting, field, 1 if setting_data.get(field) else 0)

            user_setting.updated_at = now_taiwan()
            db.session.commit()
            return success_body(), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 更新使用者設定失敗：{e}")
            return error_body("Failed to update settings", "UPDATE_SETTINGS_FAILED"), 500

    @staticmethod
    def get_medical_records(email: str):
        """取得病歷（糖尿病類型、用藥），沒有記錄就回預設值"""
        logger.info(f"[帳號:{email}] 取得病歷")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            user_medical = medical_records.query.filter_by(user_id=user.id).first()

            if user_medical:
                # 糖尿病類型：資料庫的中文轉回數字
                diabetes_type_name = safe_getattr(user_medical, "diabetes_type", "無")
                diabetes_type = 0
                for type_number, type_name in DIABETES_TYPE_NAMES.items():
                    if type_name == diabetes_type_name:
                        diabetes_type = type_number

                medical_info = {
                    "id": safe_getattr(user_medical, "id", 0),
                    "user_id": safe_getattr(user_medical, "user_id", user.id),
                    "diabetes_type": diabetes_type,
                    "oad": int(safe_getattr(user_medical, "oad", 0)),
                    "insulin": int(safe_getattr(user_medical, "insulin", 0)),
                    "anti_hypertensives": int(safe_getattr(user_medical, "anti_hypertensives", 0)),
                    "created_at": safe_datetime_str(safe_getattr(user_medical, "created_at")),
                    "updated_at": safe_datetime_str(safe_getattr(user_medical, "updated_at")),
                }
            else:
                medical_info = {
                    "id": 0,
                    "user_id": user.id,
                    "diabetes_type": 0,
                    "oad": 0,
                    "insulin": 0,
                    "anti_hypertensives": 0,
                    "created_at": "",
                    "updated_at": "",
                }

            return success_body(medical_info=medical_info), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得病歷失敗：{e}")
            return error_body("Failed to get medical records", "GET_MEDICAL_RECORDS_FAILED"), 500

    @staticmethod
    def update_medical_records(email: str, medical_data: dict):
        """更新病歷，沒有記錄就先建一筆預設值"""
        logger.info(f"[帳號:{email}] 更新病歷")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            user_medical = medical_records.query.filter_by(user_id=user.id).first()
            if not user_medical:
                user_medical = medical_records(
                    user_id=user.id,
                    diabetes_type="無",
                    oad=0.0,
                    insulin=0.0,
                    anti_hypertensives=0.0,
                    created_at=now_taiwan(),
                    updated_at=now_taiwan(),
                )
                db.session.add(user_medical)

            # 糖尿病類型：0~4 才更新，數字轉成中文存
            if "diabetes_type" in medical_data:
                diabetes_type = medical_data.get("diabetes_type")
                if diabetes_type is not None and 0 <= diabetes_type <= 4:
                    user_medical.diabetes_type = DIABETES_TYPE_NAMES.get(diabetes_type, "無")

            if "oad" in medical_data:  # 糖尿病口服藥
                user_medical.oad = 1.0 if medical_data.get("oad") else 0.0

            if "insulin" in medical_data:  # 胰島素
                user_medical.insulin = 1.0 if medical_data.get("insulin") else 0.0

            if "anti_hypertensives" in medical_data:  # 高血壓藥
                user_medical.anti_hypertensives = 1.0 if medical_data.get("anti_hypertensives") else 0.0

            user_medical.updated_at = now_taiwan()
            db.session.commit()
            return success_body(), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 更新病歷失敗：{e}")
            return error_body("Failed to update medical records", "UPDATE_MEDICAL_RECORDS_FAILED"), 500

    @staticmethod
    def update_user_badge(email: str, badge):
        """更新徽章數（存在 user_defaults.badge），0 也可以"""
        logger.info(f"[帳號:{email}] 更新徽章")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if badge is None:
                return error_body("Badge parameter cannot be empty", "BADGE_REQUIRED"), 400

            try:
                badge = int(badge)
            except (ValueError, TypeError):
                return error_body("Badge must be an integer", "BADGE_MUST_BE_INTEGER"), 400

            if badge < 0:
                return error_body("Badge cannot be negative", "BADGE_CANNOT_BE_NEGATIVE"), 400

            user_default = UserDefault.query.filter_by(user_id=user.id).first()
            if user_default:
                user_default.badge = badge
                user_default.updated_at = now_taiwan()
            else:
                db.session.add(UserDefault(
                    user_id=user.id,
                    badge=badge,
                    created_at=now_taiwan(),
                    updated_at=now_taiwan(),
                ))

            db.session.commit()
            return success_body(), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 更新徽章失敗：{e}")
            return error_body("Failed to update badge", "UPDATE_BADGE_FAILED"), 500
