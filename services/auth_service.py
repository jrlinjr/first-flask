"""
帳號認證：註冊、檢查 email、登入、驗證碼、忘記 / 重設密碼

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
from datetime import timedelta

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import SQLAlchemyError

from models.user import User
from models.friend import Friend
from services.friend_service import DEFAULT_FRIEND_GROUPS
from utils.api_response import success_body, error_body
from utils.code_generator import generate_verification_code, generate_random_password
from utils.extensions import db, bcrypt
from utils.logger import logger
from utils.mailer import send_verification_code, send_new_password
from utils.time_utils import TZ_TAIWAN, now_taiwan
from utils.validators import is_valid_email

# 驗證碼有效時間
VERIFICATION_CODE_TTL = timedelta(minutes=15)


class AuthService:

    @staticmethod
    def register(email: str, password: str, account: str | None = None):
        """
        使用者註冊

        Args:
            email: 電子郵件地址
            password: 密碼
            account: 帳號名稱（可選）
        """
        try:
            # 1. 驗證 email 格式
            if not is_valid_email(email):
                return error_body("Invalid email format", "INVALID_EMAIL_FORMAT"), 400

            # 2. 驗證密碼強度
            if len(password) < 8:
                return error_body("Password must be at least 8 characters", "PASSWORD_TOO_SHORT"), 400

            # 3. 檢查 email 是否已存在
            existing_user: User | None = User.query.filter_by(email=email).first()

            # 4. 已驗證過的帳號不能重複註冊
            if existing_user and existing_user.is_verified:
                return error_body("This email is already registered and verified", "EMAIL_REGISTERED_VERIFIED"), 409

            # 5. 檢查帳號名稱是否已被別人使用
            if account:
                account_query = User.query.filter_by(account=account)
                if existing_user:
                    account_query = account_query.filter(User.id != existing_user.id)

                if account_query.first():
                    return error_body("This account is already in use", "ACCOUNT_ALREADY_USED"), 409

            # 6. 生成密碼雜湊和驗證碼
            pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            verification_code = generate_verification_code()
            verification_expires = now_taiwan() + VERIFICATION_CODE_TTL

            # 7. 更新或建立用戶
            if existing_user:
                # 還沒驗證的帳號：更新密碼、換新驗證碼
                existing_user.password_hash = pw_hash
                existing_user.verification_code = verification_code
                existing_user.verification_code_expires = verification_expires
                if account:
                    existing_user.account = account
                status_code = 200
            else:
                user = User(
                    email=email,
                    password_hash=pw_hash,
                    account=account,
                    name=None,
                    is_verified=False,
                    verification_code=verification_code,
                    verification_code_expires=verification_expires,
                )
                db.session.add(user)
                db.session.flush()  # 先送出 INSERT 才拿得到 user.id

                # 為新使用者建立預設好友分組
                for group in DEFAULT_FRIEND_GROUPS:
                    db.session.add(Friend(
                        user_id=user.id,
                        name=group["name"],
                        relation_type=group["relation_type"],
                        created_at=now_taiwan(),
                        updated_at=now_taiwan(),
                    ))
                status_code = 201

            # 8. 提交資料庫變更
            db.session.commit()

            # 9. 寄驗證信
            try:
                send_verification_code(email, verification_code)
            except Exception as mail_error:
                logger.error(f"[帳號:{email}] 註冊驗證信寄送失敗：{mail_error}")
                return error_body(
                    "Registration successful, verification code sent to your email",
                    "REGISTRATION_SUCCESS",
                    needs_verification=True,
                ), 400

            return success_body(
                "Registration successful, verification code sent to your email",
                "REGISTRATION_SUCCESS",
                needs_verification=True,
            ), status_code

        except SQLAlchemyError as db_error:
            db.session.rollback()  # 回滾，確保交易一致性
            logger.error(f"[帳號:{email}] 註冊時資料庫錯誤：{db_error}")
            return error_body("Database error occurred", "DATABASE_ERROR"), 400

        except Exception as e:
            db.session.rollback()  # 回滾，確保交易一致性
            logger.error(f"[帳號:{email}] 註冊失敗：{e}")
            return error_body("Registration failed", "REGISTRATION_FAILED"), 400

    @staticmethod
    def check_email(email: str):
        """檢查 email 是否已註冊；已註冊但未驗證的話順便重寄驗證碼"""
        try:
            if not is_valid_email(email):
                return error_body("Invalid email format", "INVALID_EMAIL_FORMAT"), 400

            existing_user: User | None = User.query.filter_by(email=email).first()

            if existing_user:
                # 已驗證：不允許重複註冊
                if existing_user.is_verified:
                    return error_body("This email is already registered and verified", "EMAIL_REGISTERED_VERIFIED"), 400

                # 未驗證：自動重寄驗證碼
                verification_code = generate_verification_code()
                existing_user.verification_code = verification_code
                existing_user.verification_code_expires = now_taiwan() + VERIFICATION_CODE_TTL
                db.session.commit()

                try:
                    send_verification_code(email, verification_code)
                except Exception as mail_error:
                    logger.error(f"[帳號:{email}] 重寄驗證信失敗：{mail_error}")

                return success_body(
                    "This email is registered but not verified, verification code resent",
                    "EMAIL_REGISTERED_UNVERIFIED",
                    user_exists=True,
                    needs_verification=True,
                ), 200

            # Email 可用
            return success_body("Email is available", "EMAIL_AVAILABLE", user_exists=False), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 檢查 email 失敗：{e}")
            return error_body("Check failed", "CHECK_FAILED"), 500

    @staticmethod
    def login(email: str, password: str):
        try:
            if not is_valid_email(email):
                return error_body("Invalid email format", "INVALID_EMAIL_FORMAT"), 400

            if not password:
                return error_body("Password cannot be empty", "PASSWORD_REQUIRED"), 400

            user: User | None = User.query.filter_by(email=email).first()

            # 帳號不存在或密碼錯誤，回一樣的訊息（不透露是哪個錯）
            if not user or not bcrypt.check_password_hash(user.password_hash, password):
                return error_body("Incorrect username or password", "INVALID_CREDENTIALS"), 401

            # 密碼對了才檢查是否驗證過 email（放在密碼比對之後，才不會洩漏帳號是否存在）
            # 沒驗證就不發 token，避免用別人的 email 註冊後直接登入
            if not user.is_verified:
                logger.warning(f"[帳號:{email}] 未驗證 email 嘗試登入")
                return error_body("Email has not been verified", "EMAIL_NOT_VERIFIED", needs_verification=True), 403

            # 建立 JWT，用 email 當作身分（之後 get_jwt_identity() 拿到的就是 email）
            token = create_access_token(identity=email)
            return success_body("Login successful", "LOGIN_SUCCESS", token=token), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 登入失敗：{e}")
            return error_body("Login failed", "LOGIN_FAILED"), 500

    @staticmethod
    def send_verification(email: str):
        logger.info(f"[帳號:{email}] 寄送驗證碼")
        try:
            # 只取出「第一筆符合條件的資料」
            user: User | None = User.query.filter_by(email=email).first()
            if not user:
                return error_body("This email is not registered", "EMAIL_NOT_REGISTERED"), 400

            verification_code = generate_verification_code()
            user.verification_code = verification_code
            user.verification_code_expires = now_taiwan() + VERIFICATION_CODE_TTL
            db.session.commit()

            try:
                send_verification_code(email, verification_code)
            except Exception as mail_error:
                logger.error(f"[帳號:{email}] 驗證信寄送失敗：{mail_error}")

            return success_body("Verification code sent", "VERIFICATION_CODE_SENT"), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 寄送驗證碼失敗：{e}")
            return error_body("Send failed", "SEND_FAILED"), 500

    @staticmethod
    def verify_code(email: str, code: str, password):
        """檢查驗證碼，驗證碼和密碼都對才標記為已驗證

        為什麼要帶密碼：還沒驗證的帳號可以用同一個 email 重新註冊（會換掉密碼）。
        如果只看驗證碼，別人搶在本人驗證前重新註冊，本人一驗證，帳號就帶著別人設的密碼被啟用了。
        """
        logger.info(f"[帳號:{email}] 驗證驗證碼")
        try:
            # 正規化：透過 (email or "")，若 email 是 None，就會自動換成空字串 ""
            email = (email or "").strip()
            code = code or ""
            # 跟登入一樣去掉前後空白；不是字串（例如數字）就當成沒帶
            password = password.strip() if isinstance(password, str) else ""

            if not password:
                return error_body("Password cannot be empty", "PASSWORD_REQUIRED"), 400

            # 在 User 資料表裡用 email 當條件查詢，只取第一筆；找不到就是 None
            user: User | None = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            if user.verification_code != code:
                return error_body("Incorrect verification code", "VERIFICATION_CODE_INCORRECT"), 400

            # 只有當資料庫裡「驗證碼到期時間」有值時，才進行到期檢查
            if user.verification_code_expires:
                current_time = now_taiwan()  # 帶台灣時區的現在時間
                expires_time = user.verification_code_expires

                if expires_time.tzinfo is None:
                    # 資料庫讀出來的時間沒有時區資訊，補上台灣時區
                    expires_time = expires_time.replace(tzinfo=TZ_TAIWAN)
                else:
                    expires_time = expires_time.astimezone(TZ_TAIWAN)

                if expires_time < current_time:
                    return error_body("Verification code expired", "VERIFICATION_CODE_EXPIRED"), 400

            # 驗證碼對了才比對密碼（放在後面，沒有驗證碼的人就無法拿這支 API 試密碼）
            if not bcrypt.check_password_hash(user.password_hash, password):
                logger.warning(f"[帳號:{email}] 驗證碼正確但密碼錯誤")
                return error_body("Incorrect password", "INVALID_CREDENTIALS"), 401

            # 驗證成功，標記為已驗證
            user.is_verified = True
            user.verification_code = None
            user.verification_code_expires = None
            db.session.commit()

            return success_body("Verification successful", "VERIFICATION_SUCCESS"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 驗證失敗：{e}")
            return error_body("Verification failed", "VERIFICATION_FAILED"), 500

    @staticmethod
    def forgot_password(email: str):
        """忘記密碼：產生隨機新密碼寄到信箱，並標記登入後必須改密碼

        先寄信、寄成功才 commit；寄失敗就 rollback，舊密碼照樣能登入
        """
        try:
            email = (email or "").strip()

            if not is_valid_email(email):
                return error_body("Invalid email format", "INVALID_EMAIL_FORMAT"), 400

            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("This email is not registered", "EMAIL_NOT_REGISTERED"), 400

            # 隨機 8 碼新密碼（大小寫英文 + 數字）
            new_password = generate_random_password()

            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
            user.must_change_password = 1  # 必須重設密碼
            user.verification_code = None
            user.verification_code_expires = None

            try:
                send_new_password(email, new_password)
            except Exception as mail_error:
                db.session.rollback()
                logger.error(f"[帳號:{email}] 新密碼信寄送失敗，密碼不變更：{mail_error}")
                return error_body("Reset failed", "RESET_FAILED"), 500

            db.session.commit()
            return success_body("New password sent to your email", "NEW_PASSWORD_SENT"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 忘記密碼處理失敗：{e}")
            return error_body("Reset failed", "RESET_FAILED"), 500

    @staticmethod
    def reset_password(email: str, new_password: str, requested_email: str | None = None):
        """重設密碼 - 使用者登入後主動修改密碼

        Args:
            email: 登入者（JWT 身分），只會改這個帳號的密碼
            new_password: 新密碼
            requested_email: body 帶的 email（可省略）；跟登入者不同就回 403，避免改到別人的密碼
        """
        try:
            email = (email or "").strip()
            new_password = new_password or ""

            # MySQL 比對 email 不分大小寫，這裡也不分
            if requested_email is not None and requested_email.strip().lower() != email.lower():
                logger.warning(f"[帳號:{email}] 嘗試重設其他帳號的密碼：{requested_email}")
                return error_body("Cannot reset another user's password", "FORBIDDEN"), 403

            if len(new_password) < 8:
                return error_body("Password must be at least 8 characters", "PASSWORD_TOO_SHORT"), 400

            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 400

            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
            user.must_change_password = 0  # 清除必須重設密碼標記
            db.session.commit()

            return success_body("Password reset successful", "PASSWORD_RESET_SUCCESS"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 重設密碼失敗：{e}")
            return error_body("Reset failed", "RESET_FAILED"), 500
