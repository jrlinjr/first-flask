import re
import traceback
import string  
from datetime import datetime, timedelta, timezone
from flask_mail import Message
from app.models.user import User
from app.models.user_default import UserDefault
from app.models.user_setting import UserSetting
from app.models.user_vip import UserVip
from app.models.user_medical import medical_records
from app.models.a1c import A1cRecord
from app.extensions import db, bcrypt, mail
from flask_jwt_extended import create_access_token
import random
from app.models.share import ShareRecord
from app.models.news import News
from app.models.friend import Friend
from app.models.diary import Diary
from app.models.friendresult import FriendResult
import json
from time import perf_counter
from uuid import uuid4
from flask import current_app
import logging  # 添加這行
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
import hashlib
import time
# 在 import 區域添加
import gc
import psutil
import os


TZ_TAIWAN = timezone(timedelta(hours=8))
def log_memory_usage(label=""):
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        print(f"{label} Memory: {memory_info.rss / 1024 / 1024:.2f} MB")
    except:
        pass


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class AuthController:
    
    @staticmethod
    def register(email: str, password: str, account: str = None):
        print("Registering user...")
        try:
            # 正規化
            email = (email or "").strip().lower()
            password = password or ""
            account = (account or "").strip() if account else None

            # 驗證 email 格式
            if not EMAIL_RE.match(email):
                return {
                    "status": "1",
                    "message": "Invalid email format",
                    "message_code": "INVALID_EMAIL_FORMAT"
                }, 400

            # 驗證密碼長度
            if len(password) < 8:
                return {
                    "status": "1",
                    "message": "Password must be at least 8 characters",
                    "message_code": "PASSWORD_TOO_SHORT"
                }, 400

            # 檢查 email 是否已存在
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                if existing_user.is_verified:
                    return {
                        "status": "1",
                        "message": "This email is already registered and verified",
                        "message_code": "EMAIL_REGISTERED_VERIFIED"
                    }, 409
                else:
                    # 如果存在但未驗證，更新資料並重新發送驗證碼
                    if account:
                        existing_account = User.query.filter(
                            User.account == account,
                            User.id != existing_user.id
                        ).first()
                        if existing_account:
                            return {
                                "status": "1",
                                "message": "This account is already in use",
                                "message_code": "ACCOUNT_ALREADY_USED"
                            }, 409
                
                    # 更新密碼和帳號
                    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
                    existing_user.password_hash = pw_hash
                    if account:
                        existing_user.account = account
                
                    # 生成新的驗證碼
                    verification_code = str(random.randint(100000, 999999))
                    existing_user.verification_code = verification_code
                    existing_user.verification_code_expires = datetime.now(TZ_TAIWAN) + timedelta(minutes=15)
                    
                    db.session.commit()
                    
                    # 發送驗證郵件
                    try:
                        msg = Message(
                            subject="帳號驗證",
                            recipients=[email],
                            body=f"您的驗證碼是: {verification_code}，15分鐘內有效。"
                        )
                        mail.send(msg)
                    except Exception as mail_error:
                        pass
                
                return {
                    "status": "0",
                    "message": "Registration successful, verification code sent to your email",
                    "message_code": "REGISTRATION_SUCCESS",
                    "needs_verification": True
                }, 200
        
            # 檢查 account 是否已存在（如果有提供）
            if account and User.query.filter_by(account=account).first():
                return {
                    "status": "1",
                    "message": "This account is already in use",
                    "message_code": "ACCOUNT_ALREADY_USED"
                }, 409

            # 建立新使用者
            if not existing_user:  # 只有新使用者才建立
                pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
                verification_code = str(random.randint(100000, 999999))
                
                user = User(
                    email=email, 
                    password_hash=pw_hash, 
                    account=account, 
                    name=None,
                    is_verified=False,
                    verification_code=verification_code,
                    verification_code_expires=datetime.now(TZ_TAIWAN) + timedelta(minutes=15)
                )
                db.session.add(user)
                db.session.flush()  # 先 flush 以取得 user.id
                
                # 為新使用者建立預設好友
                default_friends = [
                    {"name": "醫師團", "relation_type": 0},
                    {"name": "親友團", "relation_type": 1},
                    {"name": "控糖團", "relation_type": 2}
                ]
                
                for friend_data in default_friends:
                    default_friend = Friend(
                        user_id=user.id,
                        name=friend_data["name"],
                        relation_type=friend_data["relation_type"],
                        created_at=datetime.now(TZ_TAIWAN),
                        updated_at=datetime.now(TZ_TAIWAN)
                    )
                    db.session.add(default_friend)
                
                db.session.commit()

                # 發送驗證郵件
                try:
                    msg = Message(
                        subject="帳號驗證",
                        recipients=[email],
                        body=f"您的驗證碼是: {verification_code}，15分鐘內有效。"
                    )
                    mail.send(msg)
                except Exception as mail_error:
                    pass

                return {
                    "status": "0",
                    "message": "Registration successful, verification code sent to your email",
                    "message_code": "REGISTRATION_SUCCESS",
                    "needs_verification": True
                }, 201
        
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Registration failed",
                "message_code": "REGISTRATION_FAILED"
            }, 500

    @staticmethod
    def check_email(email: str):
        print("Checking email...")
        try:
        # 正規化 email
            email = (email or "").strip().lower()
            
            # 驗證 email 格式
            if not email:
                return {
                    "status": "1",
                    "message": "Email cannot be empty",
                    "message_code": "EMAIL_REQUIRED"
                }, 400
                
            if not EMAIL_RE.match(email):
                return {
                    "status": "1",
                    "message": "Invalid email format",
                    "message_code": "INVALID_EMAIL_FORMAT"
                }, 400
            
            # 檢查 email 是否已經註冊
            existing_user = User.query.filter_by(email=email).first()
            
            if existing_user:
                # 如果已驗證，不允許重複註冊
                if existing_user.is_verified:
                    return {
                        "status": "1",
                        "message": "This email is already registered and verified",
                        "message_code": "EMAIL_REGISTERED_VERIFIED"
                    }, 409
                else:
                    # 如果未驗證，自動發送驗證碼
                    verification_code = str(random.randint(100000, 999999))
                    existing_user.verification_code = verification_code
                    existing_user.verification_code_expires = datetime.now(TZ_TAIWAN) + timedelta(minutes=15)
                    
                    db.session.commit()
                    
                    # 發送驗證郵件
                    try:
                        msg = Message(
                            subject="帳號驗證",
                            recipients=[email],
                            body=f"您的驗證碼是: {verification_code}，15分鐘內有效。"
                        )
                        mail.send(msg)
                    except Exception as mail_error:
                        pass
            
                return {
                    "status": "0",
                    "message": "This email is registered but not verified, verification code resent",
                    "message_code": "EMAIL_REGISTERED_UNVERIFIED",
                    "user_exists": True,
                    "needs_verification": True
                }, 200
    
            return {
                "status": "0",
                "message": "Email is available",
                "message_code": "EMAIL_AVAILABLE",
                "user_exists": False
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "Check failed",
                "message_code": "CHECK_FAILED"
            }, 500

    @staticmethod
    def login(email: str, password: str):
        print("Logging in user...")
        try:
            # 正規化 email
            email = (email or "").strip().lower()
            
            # 驗證 email 格式
            if not EMAIL_RE.match(email):
                return {
                    "status": "1",
                    "message": "Invalid email format",
                    "message_code": "INVALID_EMAIL_FORMAT"
                }, 400
            
            # 檢查密碼是否為空
            if not password:
                return {
                    "status": "1",
                    "message": "Password cannot be empty",
                    "message_code": "PASSWORD_REQUIRED"
                }, 400

            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            
            # 驗證使用者存在且密碼正確
            if not user or not bcrypt.check_password_hash(user.password_hash, password):
                return {
                    "status": "1",
                    "message": "Incorrect username or password",
                    "message_code": "INVALID_CREDENTIALS"
                }, 401

            # 建立 JWT，使用 email 作為 identity
            token = create_access_token(identity=email)
            
            return {
                "status": "0",
                "message": "Login successful",
                "message_code": "LOGIN_SUCCESS",
                "token": token
            }, 200
    
        except Exception as e:
            return {
                "status": "1",
                "message": "Login failed",
                "message_code": "LOGIN_FAILED"
            }, 500

    @staticmethod
    def send_verification(email: str):
        print("Sending verification code...")
        try:
            # 正規化 email
            email = (email or "").strip().lower()
            
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "This email is not registered",
                    "message_code": "EMAIL_NOT_REGISTERED"
                }, 404
            
            # 生成新的驗證碼
            verification_code = str(random.randint(100000, 999999))
            user.verification_code = verification_code
            user.verification_code_expires = datetime.now(TZ_TAIWAN) + timedelta(minutes=15)
            
            db.session.commit()
            
            # 發送驗證郵件
            try:
                msg = Message(
                    subject="帳號驗證",
                    recipients=[email],
                    body=f"您的驗證碼是: {verification_code}，15分鐘內有效。"
                )
                mail.send(msg)
            except Exception as mail_error:
                pass 
            
            return {
                "status": "0",
                "message": "Verification code sent",
                "message_code": "VERIFICATION_CODE_SENT"
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "Send failed",
                "message_code": "SEND_FAILED"
            }, 500

    @staticmethod
    def verify_code(email: str, code: str):
        print("Verifying code...")
        try:
            # 正規化
            email = (email or "").strip().lower()
            code = code or ""
            
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 檢查驗證碼
            if user.verification_code != code:
                return {
                    "status": "1",
                    "message": "Incorrect verification code",
                    "message_code": "VERIFICATION_CODE_INCORRECT"
                }, 400
            
            # 修正時間比較邏輯
            if user.verification_code_expires:
                # 確保時間比較使用一致的時區
                current_time = datetime.now(TZ_TAIWAN)
                expires_time = user.verification_code_expires
                
                # 如果資料庫中的時間沒有時區資訊，加上時區
                if expires_time.tzinfo is None:
                    expires_time = expires_time.replace(tzinfo=TZ_TAIWAN)
                else:
                    # 轉換到台灣時區
                    expires_time = expires_time.astimezone(TZ_TAIWAN)
            
                print(f"Current time: {current_time}")
                print(f"Expires time: {expires_time}")
                
                if expires_time < current_time:
                    return {
                        "status": "1",
                        "message": "Verification code expired",
                        "message_code": "VERIFICATION_CODE_EXPIRED"
                    }, 400
        
            # 驗證成功，標記為已驗證
            user.is_verified = True
            user.verification_code = None
            user.verification_code_expires = None
        
            db.session.commit()
        
            return {
                "status": "0",
                "message": "Verification successful",
                "message_code": "VERIFICATION_SUCCESS"
            }, 200
        
        except Exception as e:
            print(f"verify_code error: {str(e)}")
            print(traceback.format_exc())
            db.session.rollback()
            return {
                "status": "1",
                "message": "Verification failed",
                "message_code": "VERIFICATION_FAILED"
            }, 500

    @staticmethod
    def forgot_password(email: str):
        print("Processing forgot password...")
        try:
            # 正規化 email
            email = (email or "").strip().lower()
            
            # 驗證 email 格式
            if not EMAIL_RE.match(email):
                return {
                    "status": "1",
                    "message": "Invalid email format",
                    "message_code": "INVALID_EMAIL_FORMAT"
                }, 400
            
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "This email is not registered",
                    "message_code": "EMAIL_NOT_REGISTERED"
                }, 404
            
            # 生成隨機密碼 (8位數，包含大小寫字母和數字)
            new_password = ''.join(random.choices(
                string.ascii_uppercase + string.ascii_lowercase + string.digits, 
                k=8
            ))
            
            # 更新使用者密碼
            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
            user.must_change_password = 1  # 設置必須重設密碼標記
            user.verification_code = None  # 清除驗證碼
            user.verification_code_expires = None
            
            db.session.commit()
            
            # 發送新密碼郵件
            try:
                msg = Message(
                    subject="忘記密碼 - 新密碼",
                    recipients=[email],
                    body=f"您的新密碼是: {new_password}\n\n請登入後立即修改密碼。"
                )
                mail.send(msg)
            except Exception as mail_error:
                pass  # 移除 print
            
            return {
                "status": "0",
                "message": "New password sent to your email",
                "message_code": "NEW_PASSWORD_SENT",
                "temp_password": new_password  # 僅供測試，正式環境應移除
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Reset failed",
                "message_code": "RESET_FAILED"
            }, 500

    @staticmethod
    def reset_password(email: str, new_password: str):
        print("Resetting password...")
        """
        重設密碼 - 使用者登入後主動修改密碼
        """
        try:
            # 正規化
            email = (email or "").strip().lower()
            new_password = new_password or ""
            
            # 驗證密碼長度
            if len(new_password) < 8:
                return {
                    "status": "1", 
                    "message": "Password must be at least 8 characters",
                    "message_code": "PASSWORD_TOO_SHORT"
                }, 400
            
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 更新密碼
            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
            user.must_change_password = 0  # 清除必須重設密碼標記
            
            db.session.commit()
            
            return {
                "status": "0",
                "message": "Password reset successful",
                "message_code": "PASSWORD_RESET_SUCCESS"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Reset failed",
                "message_code": "RESET_FAILED"
            }, 500


    @staticmethod
    def get_user(email: str):
        """獲取用戶完整資訊，優化記憶體使用和錯誤處理"""
        print(f"Getting user info for email: {email}")
        log_memory_usage("Start get_user")
        
        # 確保在 Flask Application Context 中執行
        from flask import has_app_context
        if not has_app_context():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    return AuthController.get_user(email)
            except Exception as context_error:
                print(f"Failed to create app context: {context_error}")
                return {
                    "status": "1",
                    "message": "System error: Unable to create application context",
                    "message_code": "SYSTEM_ERROR"
                }, 500

        # ---- Helper Functions ----
        def ss(v, default=""):
            """安全轉換為字串"""
            return default if v is None else str(v)

        def si0(v, default=0):
            """安全轉換為整數"""
            if v is None or v == "":
                return default
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        def sf0(v, default=0.0):
            """安全轉換為浮點數，確保回傳數值而非 NaN/Inf"""
            if v is None or v == "":
                return default
            try:
                result = float(v)
                # 檢查是否為有效數值
                if result != result or result == float('inf') or result == float('-inf'):
                    return default
                return result
            except (ValueError, TypeError):
                return default

        def safe_dt(dt, fmt="%Y-%m-%d %H:%M:%S"):
            """安全轉換時間格式"""
            if not dt:
                return ""
            try:
                if isinstance(dt, str):
                    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
                        try:
                            return datetime.strptime(dt, f).strftime(fmt)
                        except ValueError:
                            continue
                    return dt
                if isinstance(dt, datetime):
                    return dt.strftime(fmt)
                if hasattr(dt, "strftime"):
                    return dt.strftime(fmt)
            except Exception as e:
                print(f"Date conversion error: {e}")
            return ""

        def generate_invite_code(user_id):
            """生成邀請碼"""
            try:
                user_id_int = int(user_id)
                user_id_str = f"{user_id_int:04d}"
                suffix = (user_id_int * 7 + 1000) % 9000 + 1000
                return user_id_str + f"{suffix:04d}"
            except Exception:
                return f"{int(user_id):08d}"

        # ---- 主要邏輯 ----
        try:
            # 1. 查詢主用戶資料
            user = User.query.filter_by(email=email).first()
            if not user:
                print(f"User not found: {email}")
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            user_id = user.id
            print(f"Found user ID: {user_id}")

            # 2. 批量查詢相關資料（減少資料庫往返）
            user_default = UserDefault.query.filter_by(user_id=user_id).first()
            user_setting = UserSetting.query.filter_by(user_id=user_id).first()
            user_vip = UserVip.query.filter_by(user_id=user_id).first()
            user_a1c = (
                A1cRecord.query
                .filter_by(user_id=user_id)
                .order_by(A1cRecord.created_at.desc())
                .first()
            )

            log_memory_usage("After database queries")

            # 3. 處理基本用戶資料
            gender_value = 1 if getattr(user, "gender", False) else 0
            invite_code = ss(getattr(user, "invite_code", None)) or generate_invite_code(user_id)
            vip_level = si0(getattr(user_vip, "level", 0)) if user_vip else 0
            user_status = "VIP" if vip_level > 0 else "general"

            # 4. 構建回應資料（優先處理核心欄位）
            user_data = {
                "id": si0(user_id),
                "name": ss(getattr(user, "name", "")),
                "account": ss(getattr(user, "account", "")),
                "email": ss(getattr(user, "email", "")),
                "phone": ss(getattr(user, "phone", "")),
                "fb_id": ss(getattr(user, "fb_id", "")),
                "status": user_status,
                "group": ss(getattr(user, "group", "0")),
                "birthday": safe_dt(getattr(user, "birthday", None), "%Y-%m-%d"),
                "height": sf0(getattr(user, "height", 0.0)),
                "weight": sf0(getattr(user, "weight", 0.0)),
                "gender": gender_value,
                "address": ss(getattr(user, "address", "")),
                "unread_records": [0, 0, 0],
                "verified": 1 if getattr(user, "is_verified", False) else 0,
                "privacy_policy": 1,
                "must_change_password": si0(getattr(user, "must_change_password", 0)),
                "fcm_id": ss(getattr(user, "fcm_id", "")),
                "login_times": si0(getattr(user, "login_times", 0)),
                "created_at": safe_dt(getattr(user, "created_at", None)),
                "updated_at": safe_dt(getattr(user, "created_at", None)),
                "invite_code": invite_code,
                "verification_code": ss(getattr(user, "verification_code", "")),
            }
            
            print(f"User data built, size: {len(str(user_data))} chars")

            default_data = {
                "id": si0(getattr(user_default, "id", 0)) if user_default else 0,
                "user_id": si0(user_id),
                "sugar_delta_max": sf0(getattr(user_default, "sugar_delta_max", 0.0)) if user_default else 0.0,
                "sugar_delta_min": sf0(getattr(user_default, "sugar_delta_min", 0.0)) if user_default else 0.0,
                "sugar_morning_max": sf0(getattr(user_default, "sugar_morning_max", 0.0)) if user_default else 0.0,
                "sugar_morning_min": sf0(getattr(user_default, "sugar_morning_min", 0.0)) if user_default else 0.0,
                "sugar_evening_max": sf0(getattr(user_default, "sugar_evening_max", 0.0)) if user_default else 0.0,
                "sugar_evening_min": sf0(getattr(user_default, "sugar_evening_min", 0.0)) if user_default else 0.0,
                "sugar_before_max": sf0(getattr(user_default, "sugar_before_max", 0.0)) if user_default else 0.0,
                "sugar_before_min": sf0(getattr(user_default, "sugar_before_min", 0.0)) if user_default else 0.0,
                "sugar_after_max": sf0(getattr(user_default, "sugar_after_max", 0.0)) if user_default else 0.0,
                "sugar_after_min": sf0(getattr(user_default, "sugar_after_min", 0.0)) if user_default else 0.0,
                "systolic_max": si0(getattr(user_default, "systolic_max", 0)) if user_default else 0,
                "systolic_min": si0(getattr(user_default, "systolic_min", 0)) if user_default else 0,
                "diastolic_max": si0(getattr(user_default, "diastolic_max", 0)) if user_default else 0,
                "diastolic_min": si0(getattr(user_default, "diastolic_min", 0)) if user_default else 0,
                "pulse_max": si0(getattr(user_default, "pulse_max", 0)) if user_default else 0,
                "pulse_min": si0(getattr(user_default, "pulse_min", 0)) if user_default else 0,
                "weight_max": sf0(getattr(user_default, "weight_max", 0.0)) if user_default else 0.0,
                "weight_min": sf0(getattr(user_default, "weight_min", 0.0)) if user_default else 0.0,
                "bmi_max": sf0(getattr(user_default, "bmi_max", 0.0)) if user_default else 0.0,
                "bmi_min": sf0(getattr(user_default, "bmi_min", 0.0)) if user_default else 0.0,
                "body_fat_max": sf0(getattr(user_default, "body_fat_max", 0.0)) if user_default else 0.0,
                "body_fat_min": sf0(getattr(user_default, "body_fat_min", 0.0)) if user_default else 0.0,
                "created_at": safe_dt(getattr(user_default, "created_at", None)) if user_default else "",
                "updated_at": safe_dt(getattr(user_default, "updated_at", None)) if user_default else "",
            }
            
            print(f"Default data built, size: {len(str(default_data))} chars")

            setting_data = {
                "id": si0(getattr(user_setting, "id", 0)) if user_setting else 0,
                "user_id": si0(user_id),
                "after_recording": si0(getattr(user_setting, "after_recording", 0)) if user_setting else 0,
                "no_recording_for_a_day": si0(getattr(user_setting, "no_recording_for_a_day", 0)) if user_setting else 0,
                "over_max_or_under_min": si0(getattr(user_setting, "over_max_or_under_min", 0)) if user_setting else 0,
                "after_meal": si0(getattr(user_setting, "after_meal", 0)) if user_setting else 0,
                "unit_of_sugar": si0(getattr(user_setting, "unit_of_sugar", 0)) if user_setting else 0,
                "unit_of_weight": si0(getattr(user_setting, "unit_of_weight", 0)) if user_setting else 0,
                "unit_of_height": si0(getattr(user_setting, "unit_of_height", 0)) if user_setting else 0,
                "created_at": safe_dt(getattr(user_setting, "created_at", None)) if user_setting else "",
                "updated_at": safe_dt(getattr(user_setting, "updated_at", None)) if user_setting else "",
            }

            vip_data = {
                "id": si0(getattr(user_vip, "id", 0)) if user_vip else 0,
                "user_id": si0(user_id),
                "level": vip_level,
                "remark": sf0(getattr(user_vip, "remark", 0.0)) if user_vip else 0.0,  # 必須是 Double
                "started_at": safe_dt(getattr(user_vip, "started_at", None)) if user_vip else "",
                "ended_at": safe_dt(getattr(user_vip, "ended_at", None)) if user_vip else "",
                "created_at": safe_dt(getattr(user_vip, "created_at", None)) if user_vip else "",
                "updated_at": safe_dt(getattr(user_vip, "updated_at", None)) if user_vip else "",
            }

            a1c_data = {
                "message": ss(getattr(user_a1c, "message", "")) if user_a1c else "",
                "latest_value": sf0(getattr(user_a1c, "A1c", 0.0)) if user_a1c else 0.0,
                "latest_date": safe_dt(getattr(user_a1c, "record_date", None)) if user_a1c else "",
            }
            
            print(f"All sub-data built successfully")

            # 5. 組裝最終回應（將 default, setting, vip, a1c 放入 user 內部）
            user_data["default"] = default_data
            user_data["setting"] = setting_data
            user_data["vip"] = vip_data
            user_data["a1c"] = a1c_data
            
            response = {
                "status": "0",
                "message": "success",
                "message_code": "SUCCESS",
                "user": user_data,
            }

            # 驗證 JSON 可序列化性
            try:
                import json
                json_str = json.dumps(response, ensure_ascii=False)
                print(f"Response size: {len(json_str)} bytes ({len(json_str)/1024:.2f} KB)")
                
                # 驗證可以重新解析
                json.loads(json_str)
                print("JSON validation: OK")
            except Exception as json_error:
                print(f"JSON serialization error: {json_error}")
                # 如果序列化失敗，回傳錯誤
                return {
                    "status": "1",
                    "message": "Data serialization error",
                    "message_code": "SERIALIZATION_ERROR"
                }, 500
            
            log_memory_usage("Before return")
            print(f"Successfully retrieved user data for ID: {user_id}")
            
            # 立即清理查詢物件
            del user, user_default, user_setting, user_vip, user_a1c
            import gc
            gc.collect()
            
            return response, 200

        except Exception as e:
            print(f"Error in get_user: {str(e)}")
            import traceback
            print(traceback.format_exc())
            log_memory_usage("Error occurred")
            return {
                "status": "1",
                "message": "Failed to get user information",
                "message_code": "GET_USER_FAILED"
            }, 500

        finally:
            # 清理資源
            try:
                db.session.remove()  # 使用 remove() 而非 close()
                print("Database session cleaned up")
            except Exception as e:
                print(f"Session cleanup warning: {e}")

            try:
                import gc
                gc.collect()
                log_memory_usage("After cleanup")
            except Exception as e:
                print(f"GC warning: {e}")


    @staticmethod
    def update_user(email: str, user_data: dict):
        print("Updating user...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 記錄更新前的狀態
            original_email = user.email

            # 更新使用者資料
            if 'name' in user_data and user_data.get('name'):  # 只有非空值才更新
                user.name = user_data.get('name')
                
            if 'birthday' in user_data and user_data.get('birthday'):  # 只有非空值才更新
                user.birthday = user_data.get('birthday')
                
            if 'height' in user_data:
                height_value = user_data.get('height')
                if height_value is not None and height_value != 0:  # 允許非零值
                    user.height = height_value
                
            if 'weight' in user_data:
                weight_value = user_data.get('weight')
                if weight_value and weight_value != '':  # 只有非空字串才處理
                    try:
                        user.weight = float(weight_value)
                    except (ValueError, TypeError):
                        pass
                    
            if 'phone' in user_data and user_data.get('phone'):  # 只有非空值才更新
                user.phone = user_data.get('phone')
            
            # Email 更新邏輯 - 絕對不允許空值
            if 'email' in user_data:
                new_email = user_data.get('email')
                
                # 如果請求中包含 email 但為空，直接忽略
                if not new_email or not new_email.strip():
                    pass  # 完全忽略這個更新
                else:
                    new_email = new_email.strip().lower()
                    if new_email != user.email:
                        existing_user = User.query.filter_by(email=new_email).first()
                        if existing_user:
                            return {
                                "status": "1",
                                "message": "This email is already in use",
                                "message_code": "EMAIL_ALREADY_USED"
                            }, 409
                        user.email = new_email
            
            if 'gender' in user_data:
                gender_value = user_data.get('gender')
                if gender_value is not None:
                    user.gender = bool(gender_value)
                
            if 'fcm_id' in user_data:
                fcm_id = user_data.get('fcm_id')
                if fcm_id:  # 只有非空值才更新
                    user.fcm_id = fcm_id
                    
            if 'group' in user_data and user_data.get('group'):
                user.group = user_data.get('group')
                
            if 'fb_id' in user_data and user_data.get('fb_id'):
                user.fb_id = user_data.get('fb_id')
                
            if 'address' in user_data and user_data.get('address'):
                user.address = user_data.get('address')
            
            # Account 更新邏輯
            if 'account' in user_data:
                new_account = user_data.get('account')
                if new_account and new_account.strip():
                    new_account = new_account.strip()
                    if new_account != user.account:
                        existing_user = User.query.filter_by(account=new_account).first()
                        if existing_user:
                            return {
                                "status": "1",
                                "message": "This account is already in use",
                                "message_code": "ACCOUNT_ALREADY_USED"
                            }, 409
                        user.account = new_account

            # 最終安全檢查 - 確保 email 絕對不會是空的
            if not user.email or user.email.strip() == '':
                user.email = original_email
            
            # 儲存到資料庫
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Update failed",
                "message_code": "UPDATE_FAILED"
            }, 500

    @staticmethod
    def update_user_setting(email: str, setting_data: dict):
        print("Updating user setting...")
        try:  
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 查詢或建立使用者設定
            user_setting = UserSetting.query.filter_by(user_id=user.id).first()
            if not user_setting:
                # 如果沒有設定記錄，建立新的
                user_setting = UserSetting(user_id=user.id)
                db.session.add(user_setting)

            # 更新設定值
            if 'after_recording' in setting_data:
                value = setting_data.get('after_recording')
                user_setting.after_recording = 1 if value else 0
                
            if 'no_recording_for_a_day' in setting_data:
                value = setting_data.get('no_recording_for_a_day')
                user_setting.no_recording_for_a_day = 1 if value else 0
                
            if 'over_max_or_under_min' in setting_data:
                value = setting_data.get('over_max_or_under_min')
                user_setting.over_max_or_under_min = 1 if value else 0
                
            if 'after_meal' in setting_data:
                value = setting_data.get('after_meal')
                user_setting.after_meal = 1 if value else 0
                
            if 'unit_of_sugar' in setting_data:
                value = setting_data.get('unit_of_sugar')
                user_setting.unit_of_sugar = 1 if value else 0
                
            if 'unit_of_weight' in setting_data:
                value = setting_data.get('unit_of_weight')
                user_setting.unit_of_weight = 1 if value else 0
                
            if 'unit_of_height' in setting_data:
                value = setting_data.get('unit_of_height')
                user_setting.unit_of_height = 1 if value else 0

            # 更新時間戳
            user_setting.updated_at = datetime.now(TZ_TAIWAN)
            
            # 儲存到資料庫
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 200
            
        except Exception as e:  
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to update settings",
                "message_code": "UPDATE_SETTINGS_FAILED"
            }, 500
        



    @staticmethod
    def get_medical_records(email: str):
        print("Getting medical records...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 查詢使用者的病歷記錄
            user_medical = medical_records.query.filter_by(user_id=user.id).first()

            # 安全的屬性取得函數
            def safe_getattr(obj, attr, default=""):
                try:
                    return getattr(obj, attr, default) or default
                except:
                    return default

            def safe_strftime(dt, format_str="%Y-%m-%d %H:%M:%S", default=""):
                if not dt:
                    return default
                try:
                    return dt.strftime(format_str)
                except:
                    return default
            
            # 建構病歷資料
            if user_medical:
                # 將糖尿病類型字串轉回數字
                diabetes_type_mapping = {
                    "無": 0,
                    "糖尿病前期": 1,
                    "第一型": 2,
                    "第二型": 3,
                    "妊娠": 4
                }
                diabetes_type_str = safe_getattr(user_medical, 'diabetes_type', '無')
                diabetes_type_int = diabetes_type_mapping.get(diabetes_type_str, 0)
                
                medical_info = {
                    "id": safe_getattr(user_medical, 'id', 0),
                    "user_id": safe_getattr(user_medical, 'user_id', user.id),
                    "diabetes_type": diabetes_type_int,
                    "oad": int(safe_getattr(user_medical, 'oad', 0)),
                    "insulin": int(safe_getattr(user_medical, 'insulin', 0)),
                    "anti_hypertensives": int(safe_getattr(user_medical, 'anti_hypertensives', 0)),
                    "created_at": safe_strftime(safe_getattr(user_medical, 'created_at')),
                    "updated_at": safe_strftime(safe_getattr(user_medical, 'updated_at'))
                }
            else:
                # 如果沒有病歷記錄，回傳預設值
                medical_info = {
                    "id": 0,
                    "user_id": user.id,
                    "diabetes_type": 0,
                    "oad": 0,
                    "insulin": 0,
                    "anti_hypertensives": 0,
                    "created_at": "",
                    "updated_at": ""
                }
    
            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "medical_info": medical_info
            }, 200
    
        except Exception as e:
            return {
                "status": "1",
                "message": "Failed to get medical records",
                "message_code": "GET_MEDICAL_RECORDS_FAILED"
            }, 500

    @staticmethod
    def update_medical_records(email: str, medical_data: dict):
        print("Updating medical records...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 查詢或建立使用者病歷記錄
            user_medical = medical_records.query.filter_by(user_id=user.id).first()
            if not user_medical:
                # 如果沒有病歷記錄，建立新的並設定預設值
                user_medical = medical_records(
                    user_id=user.id,
                    diabetes_type="無",  # 設定預設值
                    oad=0.0,            # 設定預設值
                    insulin=0.0,        # 設定預設值
                    anti_hypertensives=0.0,  # 設定預設值
                    created_at=datetime.now(TZ_TAIWAN),
                    updated_at=datetime.now(TZ_TAIWAN)
                )
                db.session.add(user_medical)

            # 更新病歷資料
            if 'diabetes_type' in medical_data:
                diabetes_type = medical_data.get('diabetes_type')
                if diabetes_type is not None and 0 <= diabetes_type <= 4:
                    # 將數字轉換為對應的字串
                    type_mapping = {
                        0: "無",
                        1: "糖尿病前期", 
                        2: "第一型",
                        3: "第二型",
                        4: "妊娠"
                    }
                    user_medical.diabetes_type = type_mapping.get(diabetes_type, "無")
        
            if 'oad' in medical_data:
                value = medical_data.get('oad')
                user_medical.oad = 1.0 if value else 0.0
            
            if 'insulin' in medical_data:
                value = medical_data.get('insulin')
                user_medical.insulin = 1.0 if value else 0.0
            
            if 'anti_hypertensives' in medical_data:
                value = medical_data.get('anti_hypertensives')
                user_medical.anti_hypertensives = 1.0 if value else 0.0

            # 更新時間戳
            user_medical.updated_at = datetime.now(TZ_TAIWAN)
            
            # 儲存到資料庫
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to update medical records",
                "message_code": "UPDATE_MEDICAL_RECORDS_FAILED"
            }, 500
        
    @staticmethod
    def add_a1c(email: str, a1c_value: float, record_date: str):
        print("Adding A1c record...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 驗證 A1c 值
            if a1c_value <= 0 or a1c_value > 20:
                return {
                    "status": "1",
                    "message": "Invalid HbA1c value",
                    "message_code": "INVALID_HBA1C"
                }, 400
            
            # 解析日期
            try:
                record_date_parsed = datetime.strptime(record_date, "%Y-%m-%d").date()
            except ValueError:
                return {
                    "status": "1",
                    "message": "Date format error, should be YYYY-MM-DD",
                    "message_code": "INVALID_DATE_FORMAT"
                }, 400
            
            # 檢查是否已有相同日期的記錄
            existing_record = A1cRecord.query.filter_by(
                user_id=user.id,
                record_date=record_date_parsed
            ).first()
            
            if existing_record:
                # 更新現有記錄
                existing_record.A1c = a1c_value
                existing_record.updated_at = datetime.now(TZ_TAIWAN)
            else:
                # 新增 HbA1c 記錄
                new_a1c = A1cRecord(
                    user_id=user.id,
                    A1c=a1c_value,
                    record_date=record_date_parsed
                )
                db.session.add(new_a1c)
        
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to add HbA1c record",
                "message_code": "ADD_HBA1C_FAILED"
            }, 500
        
    @staticmethod
    def get_a1c_records(email: str):
        print("Getting A1c records...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 查詢 HbA1c 記錄
            a1c_records = A1cRecord.query.filter_by(user_id=user.id).order_by(A1cRecord.record_date.desc()).all()

            # 格式化回應資料
            records_list = []
            for record in a1c_records:
                records_list.append({
                    "id": record.id,
                    "user_id": record.user_id,
                    "a1cs": str(record.a1cs),  
                    "record_date": record.record_date.strftime("%Y-%m-%d"),
                    "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                })

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "a1cs": records_list  
            }, 200
            
        except Exception as e:
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "Failed to get HbA1c records",
                "message_code": "GET_HBA1C_FAILED"
            }, 500
        

    @staticmethod
    def add_care_record(email: str, care_data: str):
        print("Adding care record...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 驗證 care_data
            if not care_data or not care_data.strip():
                return {
                    "status": "1",
                    "message": "Care data cannot be empty",
                    "message_code": "CARE_DATA_REQUIRED"
                }, 400

            # 檢查是否已有相同的照護紀錄
            existing_record = A1cRecord.query.filter_by(
                user_id=user.id,
                care_data=care_data.strip()
            ).first()

            if existing_record:
                existing_record.updated_at = datetime.now(TZ_TAIWAN)
            else:
                # 新增 Care 記錄
                new_care = A1cRecord(
                    user_id=user.id,
                    care_data=care_data.strip()
            )
            db.session.add(new_care)
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to add care record",
                "message_code": "ADD_CARE_FAILED"
            }, 500
        

    @staticmethod
    def get_care_records(email: str):
        print("Getting care records...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 查詢 Care 記錄
            care_records = A1cRecord.query.filter_by(user_id=user.id).order_by(A1cRecord.created_at.desc()).all()

            # 格式化回應資料
            records_list = []
            for record in care_records:
                records_list.append({
                    "id": record.id,
                    "user_id": record.user_id,
                    "cares": record.care_data,
                    "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                })

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "cares": records_list
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "Failed to get care records",
                "message_code": "GET_CARE_FAILED"
            }, 500



    @staticmethod
    def add_share_record(email: str, record_type: int, record_id: int, relation_type: int):
        print("Adding share record...")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            print(f"Adding share record for user {user.id}: type={record_type}, id={record_id}, relation_type={relation_type}")
            
            # 驗證輸入參數
            if record_type not in [0, 1, 2, 3]:
                return {
                    "status": "1",
                    "message": "Invalid type parameter",
                    "message_code": "INVALID_TYPE"
                }, 400

            if relation_type not in [0, 1, 2]:
                return {
                    "status": "1",
                    "message": "Invalid relation_type parameter",
                    "message_code": "INVALID_RELATION_TYPE"
                }, 400
                
            if not record_id or record_id <= 0:
                return {
                    "status": "1",
                    "message": "Invalid record_id parameter",
                    "message_code": "INVALID_RECORD_ID"
                }, 400
            
            # 查詢使用者是否有對應類型的好友
            friend_count = Friend.query.filter_by(
                user_id=user.id,
                relation_type=relation_type
            ).count()
            
            print(f"User {user.id} has {friend_count} friends of type {relation_type}")

            # 檢查是否有對應類型的好友
            if friend_count == 0:
                relation_names = {0: "醫師團", 1: "親友團", 2: "控糖團"}
                print(f"User {user.id} has no friends of type {relation_type}")
                return {
                    "status": "1", 
                    "message": f"請先新增{relation_names.get(relation_type, '好友')}"
                }, 400
            
            print(f"Friend count check passed, proceeding to check existing share")
            
            # 檢查是否已經分享過相同記錄
            existing_share = ShareRecord.query.filter_by(
                user_id=user.id,
                record_type=record_type,
                record_id=record_id,
                relation_type=relation_type
            ).first()
            
            print(f"Checking for existing share record...")
            
            if existing_share:
                print(f"Share record already exists: {existing_share.id}, updating timestamp")
                # 修正：允許更新分享時間，而不是返回錯誤
                existing_share.shared_at = datetime.now(TZ_TAIWAN)
                existing_share.updated_at = datetime.now(TZ_TAIWAN)
                db.session.commit()
                
                return {
                    "status": "0",
                    "message": "Update share successful",
                    "message_code": "UPDATE_SHARE_SUCCESS"
                }, 200
            
            print(f"Creating new share record...")
            
            # 建立新的分享記錄
            new_share = ShareRecord(
                user_id=user.id,
                record_type=record_type,
                record_id=record_id,
                relation_type=relation_type,
                shared_at=datetime.now(TZ_TAIWAN),
                created_at=datetime.now(TZ_TAIWAN),
                updated_at=datetime.now(TZ_TAIWAN)
            )
            
            db.session.add(new_share)
            db.session.commit()
            
            print(f"Share record created successfully: {new_share.id}")

            return {
                "status": "0",
                "message": "Share successful",
                "message_code": "SHARE_SUCCESS"
            }, 200
            
        except Exception as e:
            print(f"add_share_record error: {str(e)}")
            print(traceback.format_exc())
            db.session.rollback()
            return {
                "status": "1",
                "message": "Share failed",
                "message_code": "SHARE_FAILED"
            }, 500










    # 新增輔助方法：檢查使用者是否有特定關係類型的好友
    @staticmethod
    def has_friend_in_relation(user_id: int, relation_type: int) -> bool:
        """
        檢查使用者是否有指定關係類型的好友
        """
        try:
            # 查詢該使用者是否有指定類型的好友
            friend = Friend.query.filter_by(
                user_id=user_id,
                relation_type=relation_type
            ).first()
            
            # 如果有找到好友記錄，返回 True
            return friend is not None
            
        except Exception as e:
            print(f"Check friend relation error: {str(e)}")
            return False


    @staticmethod
    def get_shared_records(email: str, relation_type):
        print(f"=== GET SHARED RECORDS START ===")
        print(f"Email: {email}, relation_type: {relation_type}")
        log_memory_usage("Start get_shared_records")
        
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {"status": "1", "message": "User not found",
                "message_code": "USER_NOT_FOUND"}, 404

            # 參數轉換
            try:
                relation_type_int = int(str(relation_type).strip())
                if relation_type_int not in [0, 1, 2]:
                    return {"status": "1", "message": "Invalid relation_type parameter",
                    "message_code": "INVALID_RELATION_TYPE"}, 400
            except (ValueError, TypeError):
                return {"status": "1", "message": "Invalid relation_type parameter format",
                "message_code": "INVALID_RELATION_TYPE_FORMAT"}, 400

            print(f"User ID: {user.id}, relation_type: {relation_type_int}")

            # 🔧 新增:查詢當前用戶的好友列表(該 relation_type 的好友)
            # 查詢雙向好友關係:我發出的 + 我收到的
            my_friends_sent = FriendResult.query.filter_by(
                user_id=user.id,
                type=relation_type_int,
                status=1  # 已接受
            ).all()
            
            my_friends_received = FriendResult.query.filter_by(
                relation_id=user.id,
                type=relation_type_int,
                status=1  # 已接受
            ).all()
            
            # 收集所有好友的 user_id
            friend_ids = set()
            for fr in my_friends_sent:
                friend_ids.add(fr.relation_id)
            for fr in my_friends_received:
                friend_ids.add(fr.user_id)
            
            print(f"Found {len(friend_ids)} friends with relation_type={relation_type_int}: {friend_ids}")

            if not friend_ids:
                print("No friends found for this relation_type")
                return {"status": "0", "message": "Success",
                "message_code": "SUCCESS", "records": []}, 200

            # 🔧 修改:只查詢好友分享給該 relation_type 的記錄
            # 🚀 性能優化:使用 joinedload 預先載入分享者資訊,避免N+1查詢
            share_records = (ShareRecord.query
                .options(joinedload(ShareRecord.user))  # 預先載入分享者資訊
                .filter(
                    ShareRecord.user_id.in_(friend_ids),  # 只查詢我的好友分享的
                    ShareRecord.relation_type == relation_type_int  # 分享給該 relation_type 的
                )
                .order_by(ShareRecord.created_at.desc())
                .limit(50)
                .all()
            )
            
            print(f"📊 Found {len(share_records)} share records from friends")
            print(f"📊 Share records details:")
            for sr in share_records:
                print(f"  - ShareRecord {sr.id}: user_id={sr.user_id}, record_type={sr.record_type}, record_id={sr.record_id}, relation_type={sr.relation_type}")
            log_memory_usage("After query in get_shared_records")

            if not share_records:
                return {"status": "0", "message": "Success",
                "message_code": "SUCCESS", "records": []}, 200

            # 修正的時間格式化函數
            def safe_datetime_simple(dt):
                try:
                    if dt is None:
                        return ""
                    
                    # 檢查是否為日期時間物件
                    if not hasattr(dt, 'strftime'):
                        # 如果不是日期時間物件，直接返回空字串
                        return ""
                    
                    # 確保 datetime 物件有時區資訊
                    if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
                        # 如果沒有時區資訊，假設是台灣時區
                        dt = dt.replace(tzinfo=TZ_TAIWAN)
                    elif hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                        # 如果有時區資訊，轉換到台灣時區
                        dt = dt.astimezone(TZ_TAIWAN)
                    
                    # 使用標準格式
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                except AttributeError as e:
                    # datetime 物件沒有預期的屬性
                    print(f"DateTime attribute error: {e}")
                    return ""
                except ValueError as e:
                    # strftime 格式錯誤
                    print(f"DateTime format error: {e}")
                    return ""
                except Exception as e:
                    # 其他未預期的錯誤
                    print(f"Unexpected datetime error: {e}")
                    return ""

            # 安全的數值獲取函數
            def safe_get(obj, attr, default=0):
                try:
                    if obj is None:
                        return default
                    value = getattr(obj, attr, default)
                    return value if value is not None else default
                except Exception as e:
                    print(f"Error getting attribute {attr}: {e}")
                    return default

            # 簡化的記錄處理
            records_list = []
            for share in share_records:
                try:
                    # 🔧 使用 relationship 獲取分享者資訊(已通過joinedload預先載入)
                    sharer = share.user
                    if not sharer:
                        print(f"❌ Sharer user {share.user_id} not found, skipping record {share.id}")
                        continue
                    
                    # 🔧 使用 relationship 獲取 diary 記錄(已在模型中設定為joined)
                    diary = share.diary
                    
                    # 🔧 添加調試日誌
                    print(f"📝 Processing ShareRecord:")
                    print(f"  - ShareRecord ID: {share.id}")
                    print(f"  - Sharer: {sharer.name} (ID: {share.user_id})")
                    print(f"  - Record Type: {share.record_type}")
                    print(f"  - Diary Record ID: {share.record_id}")
                    print(f"  - Relation Type: {share.relation_type}")
                    if diary:
                        print(f"  - Diary exists: ID={diary.id}, Sugar={diary.sugar}, Weight={diary.weight}")
                    else:
                        print(f"  - ⚠️ Diary not found for record_id={share.record_id}")

                    # 🔧 構建記錄資料,包含分享者資訊
                    record_data = {
                        "id": share.id,
                        "user_id": share.user_id,
                        "relation_id": safe_get(share, "relation_id", 0),
                        # 🎯 分享者的資訊
                        "user": {
                            "id": sharer.id,
                            "name": safe_get(sharer, "name", ""),
                            "email": safe_get(sharer, "email", ""),
                            "account": safe_get(sharer, "account", "")
                        },
                        "type": safe_get(share, "record_type", 0),
                        "record_type": safe_get(share, "record_type", 0),
                        "weight": float(safe_get(diary, "weight", 0)),
                        "body_fat": float(safe_get(diary, "body_fat", 0)),
                        "sugar": float(safe_get(diary, "sugar", 0)),
                        "meal_type": int(safe_get(diary, "meal", 0)),
                        "bmi": float(safe_get(diary, "bmi", 0)),
                        "shared_at": safe_datetime_simple(share.shared_at),
                        "recorded_at": safe_datetime_simple(safe_get(diary, "recorded_at")),
                        "created_at": safe_datetime_simple(safe_get(diary, "created_at")),
                        "meal": int(safe_get(diary, "meal", 0)),
                        "timeperiod": int(safe_get(diary, "timeperiod", 0)),
                        "tag": [[]],
                        "image": [],
                        "location": {"lat": "", "lng": "", "address": ""},
                        "relation_type": safe_get(share, "relation_type", 0),
                        "systolic": int(safe_get(diary, "systolic", 0)),
                        "diastolic": int(safe_get(diary, "diastolic", 0)),
                        "pulse": int(safe_get(diary, "pulse", 0)),
                        "message": str(safe_get(diary, "description", "")),
                        "url": "",
                        "record_status": 0
                    }
                    
                    records_list.append(record_data)
                    print(f"Successfully processed record {share.id}")
                    
                    # 立即清理 diary 物件以節省記憶體
                    diary = None
                    
                except Exception as e:
                    print(f"Error processing share record {share.id}: {e}")
                    continue

            print(f"=== RETURNING {len(records_list)} RECORDS ===")
            log_memory_usage("End get_shared_records")
            return {"status": "0", "message": "Success",
            "message_code": "SUCCESS", "records": records_list}, 200

        except Exception as e:
            print(f"Critical error in get_shared_records: {str(e)}")
            import traceback
            traceback.print_exc()
            log_memory_usage("Error in get_shared_records")
            return {"status": "1", "message": "Failed to get share records",
            "message_code": "GET_SHARE_RECORDS_FAILED"}, 500
        finally:
            # 強制記憶體清理
            try:
                import gc
                # 清理局部變數
                locals_to_clear = ['user', 'share_records', 'records_list', 'diary']
                for var_name in locals_to_clear:
                    if var_name in locals():
                        locals()[var_name] = None
                
                # 強制垃圾回收
                collected = gc.collect()
                print(f"GC collected {collected} objects in get_shared_records cleanup")
                
                # 記錄清理後的記憶體狀況
                log_memory_usage("After get_shared_records cleanup")
                
            except Exception as cleanup_error:
                print(f"Cleanup error in get_shared_records: {cleanup_error}")


    @staticmethod
    def get_news(email: str):
        print("Getting news...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 查詢最新消息（可以根據群組或全部顯示）
            news_records = News.query.order_by(News.created_at.desc()).all()
            
            # 格式化回應資料
            news_list = []
            for news in news_records:
                # 安全的時間格式化
                def safe_strftime(dt, format_str="%Y-%m-%d %H:%M:%S", default=""):
                    if not dt:
                        return default
                    try:
                        return dt.strftime(format_str)
                    except:
                        return default
                
                # 安全的字符串處理 - 避免中文字符
                def safe_string(text, default=""):
                    if not text:
                        return default
                    try:
                        # 檢查是否含有非ASCII字符
                        text.encode('ascii')
                        return text
                    except UnicodeEncodeError:
                        # 如果包含中文或其他非ASCII字符，返回安全的替代文本
                        return f"Content {news.id}"
            
                news_data = {
                    "id": news.id,
                    "member_id": news.member_id,
                    "group": news.group,
                    "title": safe_string(news.title, f"News {news.id}"),
                    "message": safe_string(news.message, "Content available"),
                    "pushed_at": safe_strftime(news.pushed_at),
                    "created_at": safe_strftime(news.created_at),
                    "updated_at": safe_strftime(news.updated_at)
                }
                
                news_list.append(news_data)

            return {
                "status": "0",
                "message": "News retrieved successfully",
                "message_code": "SUCCESS",
                "news": news_list
            }, 200
            
        except Exception as e:
            print(f"Get news error: {str(e)}")
            return {
                "status": "1",
                "message": "Failed to get news",
                "message_code": "GET_NEWS_FAILED"
            }, 500


    @staticmethod
    def get_friend_list(email: str):
        print("Getting friend list...")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {"status": "1", "message": "User not found", "message_code": "USER_NOT_FOUND"}, 404
            
            # 查詢所有雙向關係中，狀態為 1 (已接受) 的紀錄
            # 預先載入對方的使用者資料 (user 和 relation_user)
            friend_relations = (
                FriendResult.query
                .options(joinedload(FriendResult.user), joinedload(FriendResult.relation_user))
                .filter(
                    db.or_(FriendResult.user_id == user.id, FriendResult.relation_id == user.id),
                    FriendResult.status == 1
                )
            ).all()

            friends_list = []
            seen_friend_ids = set() # 用來避免重複加入同一個好友

            for fr in friend_relations:
                friend_user = None
                # 判斷對方是誰
                if fr.user_id == user.id:
                    friend_user = fr.relation_user
                else:
                    friend_user = fr.user
                
                #【防呆】如果好友 user 物件不存在，或已經加過了，就跳過
                if not friend_user or friend_user.id in seen_friend_ids:
                    continue
                
                seen_friend_ids.add(friend_user.id)

                relation_type_map = {0: "醫師團", 1: "親友團", 2: "控糖團"}
                
                friends_list.append({
                    "id": friend_user.id,
                    "name": friend_user.name or friend_user.account or f"User {friend_user.id}",
                    "relation_type": fr.type,
                    "relation_type_name": relation_type_map.get(fr.type, "general"),
                    "email": friend_user.email or "",
                    "created_at": fr.created_at.isoformat() if fr.created_at else ""
                })

            return {"status": "0", "message": "Success", "message_code": "SUCCESS", "friends": friends_list}, 200

        except Exception as e:
            print(f"Get friend list error: {str(e)}")
            traceback.print_exc()
            return {"status": "1", "message": "Failed to get friends list", "message_code": "GET_FRIENDS_LIST_FAILED"}, 500
    
    @staticmethod
    def add_friend(email: str, friend_name: str, relation_type: int = 0):
        print("Adding friend...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 驗證輸入
            if not friend_name or not friend_name.strip():
                return {
                    "status": "1",
                    "message": "Friend name cannot be empty",
                    "message_code": "FRIEND_NAME_REQUIRED"
                }, 400
            
            # 驗證 relation_type
            if relation_type not in [0, 1, 2]:
                return {
                    "status": "1",
                    "message": "Invalid relation_type parameter",
                    "message_code": "INVALID_RELATION_TYPE"
                }, 400
            
            # 檢查是否已存在相同名稱的好友
            existing_friend = Friend.query.filter_by(
                user_id=user.id,
                name=friend_name.strip()
            ).first()
            
            if existing_friend:
                return {
                    "status": "1",
                    "message": "Friend already exists",
                    "message_code": "FRIEND_ALREADY_EXISTS"
                }, 409
            
            # 建立新好友
            new_friend = Friend(
                user_id=user.id,
                name=friend_name.strip(),
                relation_type=relation_type,
                created_at=datetime.now(TZ_TAIWAN),
                updated_at=datetime.now(TZ_TAIWAN)
            )
            db.session.add(new_friend)
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to add friend",
                "message_code": "ADD_FRIEND_FAILED"
            }, 500

    @staticmethod
    def get_diary_entries(email: str, date: str = None):
        print("Getting diary entries...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 建立查詢
            query = Diary.query.filter_by(user_id=user.id)

            # 如果有提供日期，篩選特定日期
            if date:
                try:
                    target_date = datetime.strptime(date, "%Y-%m-%d").date()
                    query = query.filter(
                        db.func.date(Diary.recorded_at) == target_date
                    )
                except ValueError:
                    return {
                        "status": "1",
                        "message": "Date format error, should be YYYY-MM-DD",
                        "message_code": "INVALID_DATE_FORMAT"
                    }, 400

            diary_records = query.order_by(Diary.recorded_at.desc()).all()

            # 安全的時間格式化
            def safe_strftime(dt, format_str="%Y-%m-%d %H:%M:%S", default=""):
                if not dt:
                    return default
                try:
                    return dt.strftime(format_str)
                except:
                    return default

            # 安全的 JSON 解析
            def safe_json_parse(json_data, default=None):
                if json_data is None:
                    return default
                if isinstance(json_data, (dict, list)):
                    return json_data
                try:
                    return json.loads(json_data) if isinstance(json_data, str) else json_data
                except:
                    return default

            # 格式化回應資料
            diary_list = []
            for diary in diary_records:
                try:  # 為每筆記錄加上錯誤處理
                    tag_raw = safe_json_parse(diary.tag, {"name": [], "message": ""})
                    if isinstance(tag_raw, dict):
                        tag_array = [tag_raw]
                    elif isinstance(tag_raw, list):
                        tag_array = tag_raw
                    else:
                        tag_array = [{"name": [], "message": ""}]

                    # 修正：將 image_array 處理移到 for 迴圈內
                    image_array = safe_json_parse(diary.image, [])
                    if not isinstance(image_array, list):
                        image_array = []

                    # 修正：將 diary_data 處理移到 for 迴圈內
                    diary_data = {
                        "id": diary.id,
                        "user_id": diary.user_id,
                        "systolic": diary.systolic or 0,
                        "diastolic": diary.diastolic or 0,
                        "pulse": diary.pulse or 0,
                        "weight": float(diary.weight or 0.0),
                        "body_fat": float(diary.body_fat or 0.0),
                        "bmi": float(diary.bmi or 0.0),
                        "sugar": float(diary.sugar or 0.0),
                        "exercise": diary.exercise or 0,
                        "drug": diary.drug or 0,
                        "timeperiod": diary.timeperiod or 0,
                        "description": diary.description or "",
                        "meal": diary.meal or 0,
                        "tag": tag_array,
                        "image": image_array,
                        "location": {
                            "lat": str(safe_json_parse(diary.location, {}).get("lat", "") or ""),
                            "lng": str(safe_json_parse(diary.location, {}).get("lng", "") or "")
                            },
                        "reply": diary.reply or "",
                        "recorded_at": safe_strftime(diary.recorded_at),
                        "type": diary.type or ""
                    }
                    diary_list.append(diary_data)
                    
                except Exception as record_error:
                    print(f"Error processing diary record {diary.id}: {record_error}")
                    continue  # 跳過有問題的記錄

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "diary": diary_list
            }, 200

        except Exception as e:
            print(f"Get diary error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "Failed to get diary entries",
                "message_code": "GET_DIARY_FAILED"
            }, 500
    
    @staticmethod
    def update_user_badge(email: str, badge: int):
        print("Updating user badge...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 驗證 badge 參數 - 允許 badge 為 0
            if badge is None:
                return {
                    "status": "1",
                    "message": "Badge parameter cannot be empty",
                    "message_code": "BADGE_REQUIRED"
                }, 400
            
            # 驗證 badge 是否為有效整數
            try:
                badge = int(badge)
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "Badge must be an integer",
                    "message_code": "BADGE_MUST_BE_INTEGER"
                }, 400
            
            # 修正：允許 badge 為 0，只檢查是否小於 0
            if badge < 0:
                return {
                    "status": "1",
                    "message": "Badge cannot be negative",
                    "message_code": "BADGE_CANNOT_BE_NEGATIVE"
                }, 400
            
            # 檢查是否有 user_default 記錄
            user_default = UserDefault.query.filter_by(user_id=user.id).first()
            
            if user_default:
                # 更新現有記錄
                user_default.badge = badge
                user_default.updated_at = datetime.now(TZ_TAIWAN)
            else:
                # 建立新記錄
                user_default = UserDefault(
                    user_id=user.id,
                    badge=badge,
                    created_at=datetime.now(TZ_TAIWAN),
                    updated_at=datetime.now(TZ_TAIWAN)
                )
                db.session.add(user_default)
            
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 200

        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to update badge",
                "message_code": "UPDATE_BADGE_FAILED"
            }, 500

    @staticmethod
    def get_user_records(email: str, diet: int = None):
        print("Getting user records...")

        try:
        # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 驗證 diet 參數
            if diet is not None:
                try:
                    diet = int(diet)
                except (ValueError, TypeError):
                    return {
                        "status": "1",
                        "message": "Diet parameter must be an integer",
                        "message_code": "DIET_MUST_BE_INTEGER"
                    }, 400
            
            # 建立查詢條件
            query = Diary.query.filter_by(user_id=user.id)
            
            # 如果有提供 diet 參數，按時段篩選
            if diet is not None:
                query = query.filter(Diary.timeperiod == diet)
            
            # 查詢記錄，按時間排序（最新的在前）
            records = query.order_by(Diary.recorded_at.desc()).all()
            
            # 初始化回傳資料結構
            blood_sugars = {"sugar": 0.0}
            blood_pressures = {"systolic": 0, "diastolic": 0, "pulse": 0}
            weights = {"weight": 0.0}
            
            # 處理記錄資料
            for record in records:
                # 取得最新的血糖記錄
                if record.sugar is not None and record.sugar > 0 and blood_sugars["sugar"] == 0.0:
                    blood_sugars["sugar"] = float(record.sugar)
                
                # 取得最新的血壓記錄
                if (record.systolic is not None and record.systolic > 0 and 
                    blood_pressures["systolic"] == 0):
                    blood_pressures["systolic"] = int(record.systolic)
                    blood_pressures["diastolic"] = int(record.diastolic or 0)
                    blood_pressures["pulse"] = int(record.pulse or 0)
                
                # 取得最新的體重記錄
                if record.weight is not None and record.weight > 0 and weights["weight"] == 0.0:
                    weights["weight"] = float(record.weight)
                
                # 如果所有資料都已找到，可以提早結束
                if (blood_sugars["sugar"] > 0 and 
                    blood_pressures["systolic"] > 0 and 
                    weights["weight"] > 0):
                    break

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "blood_sugars": blood_sugars,
                "blood_pressures": blood_pressures,
                "weights": weights
            }, 200
            
        except Exception as e:
            print(f"Get user records error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "Failed to get health records",
                "message_code": "GET_HEALTH_RECORDS_FAILED"
            }, 500



    @staticmethod
    def add_blood_sugar(email: str, sugar: float, timeperiod: int = None, recorded_at: str = None, drug: int = None, exercise: int = None):
        print("Adding blood sugar record...")
        try:
        # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404
            
            # 驗證必要參數
            if sugar is None:
                return {
                    "status": "1",
                    "message": "Sugar parameter cannot be empty",
                    "message_code": "SUGAR_REQUIRED"
                }, 400
            
            # 驗證血糖值
            try:
                sugar = float(sugar)
                if sugar <= 0 or sugar > 1000:
                    return {
                        "status": "1",
                        "message": "Invalid blood sugar value",
                        "message_code": "INVALID_BLOOD_SUGAR"
                    }, 400
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "Blood sugar value must be a number",
                    "message_code": "BLOOD_SUGAR_MUST_BE_NUMBER"
                }, 400
            
            # 處理記錄時間
            if recorded_at:
                try:
                    recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    recorded_datetime = recorded_datetime.replace(tzinfo=TZ_TAIWAN)  # 修正：使用台灣時區
                except ValueError:
                    return {
                        "status": "1",
                        "message": "Invalid recorded_at format, should be YYYY-MM-DD HH:MM:SS",
                        "message_code": "INVALID_RECORDED_AT_FORMAT"
                    }, 400
            else:
                recorded_datetime = datetime.now(TZ_TAIWAN)  # 修正：使用台灣時區
            
            # 建立血糖記錄
            new_blood_sugar = Diary(
                user_id=user.id,
                sugar=sugar,
                timeperiod=timeperiod or 0,
                drug=drug or 0,
                exercise=exercise or 0,
                type="blood_sugar",
                recorded_at=recorded_datetime,
                created_at=datetime.now(TZ_TAIWAN),
                updated_at=datetime.now(TZ_TAIWAN)
            )
            
            db.session.add(new_blood_sugar)
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "new_record_id": new_blood_sugar.id  # 回傳新記錄的 ID
            }, 200
        
        except Exception as e:
            db.session.rollback()
            print(f"Add blood sugar error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "Failed to add blood sugar record",
                "message_code": "ADD_BLOOD_SUGAR_FAILED"
            }, 500


    @staticmethod
    def get_friend_results(email: str):
        print("Getting friend results...")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {"status": "1", "message": "User not found", "message_code": "USER_NOT_FOUND"}, 404

            # 🔧 修復：只查詢待處理(status=0)或未讀(read=0)的邀請結果
            # 已接受且已讀的邀請不再返回,避免前端重複顯示
            sent_invites = (
                FriendResult.query
                .options(joinedload(FriendResult.relation_user)) # 預先載入被我邀請的人
                .filter(
                    FriendResult.user_id == user.id,
                    # 只返回: 1) 待處理的邀請 或 2) 未讀的邀請結果
                    db.or_(
                        FriendResult.status == 0,  # 待處理
                        FriendResult.read == 0      # 未讀的結果(包含已接受/已拒絕但未讀)
                    )
                )
                .order_by(FriendResult.created_at.desc())
                .all()
            )

            print(f"Found {len(sent_invites)} friend result records for user {user.id}")

            results_list = []
            for invite in sent_invites:
                invited_user = invite.relation_user
                
                #【防呆】如果被邀請的使用者不存在，就跳過
                if not invited_user:
                    continue

                results_list.append({
                    "id": invite.id,
                    "user_id": invite.user_id,
                    "relation_id": invite.relation_id,
                    "type": invite.type,
                    "status": invite.status,
                    "read": invite.read,
                    "created_at": invite.created_at.strftime("%Y-%m-%d %H:%M:%S") if invite.created_at else "",
                    "updated_at": invite.updated_at.strftime("%Y-%m-%d %H:%M:%S") if invite.updated_at else "",
                    "relation": {
                        "id": invited_user.id,
                        "name": invited_user.name or "",
                        "account": invited_user.account or ""
                    }
                })

            print(f"Returning {len(results_list)} friend results")
            return {"status": "0", "message": "success", "message_code": "SUCCESS", "results": results_list}, 200

        except Exception as e:
            print(f"Get friend results error: {str(e)}")
            traceback.print_exc()
            return {"status": "1", "message": "system error", "message_code": "SYSTEM_ERROR"}, 500


    @staticmethod
    def get_friend_requests(email: str):
        print("Getting friend requests...")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {"status": "1", "message": "User not found", "message_code": "USER_NOT_FOUND"}, 404

            # 使用 joinedload 預先載入邀請發送者的資料，避免 N+1 查詢
            friend_requests = (
                FriendResult.query
                .options(joinedload(FriendResult.user))
                .filter_by(relation_id=user.id, status=0) # 只查詢待處理的
                .order_by(FriendResult.created_at.desc())
                .all()
            )

            requests_list = []
            for req in friend_requests:
                # 因為用了 joinedload，可以直接存取 req.user，且不會觸發額外查詢
                from_user = req.user
                
                #【防呆】如果邀請者 user 莫名被刪除，就跳過這筆邀請，避免崩潰
                if not from_user:
                    print(f"Warning: Skipping friend request {req.id} because inviter user {req.user_id} not found.")
                    continue

                requests_list.append({
                    "id": req.id,
                    "user_id": req.user_id,
                    "relation_id": req.relation_id,
                    "type": req.type,
                    "status": req.status,
                    "read": req.read,
                    "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "",
                    "updated_at": req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.updated_at else "",
                    "user": {
                        "id": from_user.id,
                        "name": from_user.name or "",
                        "account": from_user.account or ""
                    }
                })

            return {"status": "0", "message": "Success", "message_code": "SUCCESS", "requests": requests_list}, 200

        except Exception as e:
            print(f"Get friend requests error: {str(e)}")
            traceback.print_exc()
            return {"status": "1", "message": "Failed to get invitation list", "message_code": "GET_INVITATIONS_FAILED"}, 500

    # @staticmethod
    # def get_friend_requests(email: str):
    #     print("Getting friend requests...")
    #     try:
    #         user = User.query.filter_by(email=email).first()
    #         if not user:
    #             return {"status": "1", "message": "User not found",
    #                     "message_code": "USER_NOT_FOUND"}, 404

    #         friend_requests = (
    #             FriendResult.query
    #             .filter_by(relation_id=user.id, status=0)
    #             .order_by(FriendResult.created_at.desc())
    #             .all()
    #         )

    #         try:
    #             from datetime import UTC as _UTC
    #             TZ = _UTC
    #         except Exception:
    #             from datetime import timezone
    #             TZ = timezone.utc

    #         def safe_strftime(dt, fmt="%Y-%m-%d %H:%M:%S"):
    #             if not isinstance(dt, datetime):
    #                 return ""
    #             if dt.tzinfo is not None:
    #                 return dt.astimezone(TZ).strftime(fmt)
    #             return dt.strftime(fmt)

    #         requests_list = []
    #         for req in friend_requests:
    #             from_user = User.query.filter_by(id=req.user_id).first()

    #             # 確保字串，不回傳 null
    #             user_info = {
    #                 "id": req.user_id,
    #                 "name": (getattr(from_user, "name", "") or ""),
    #                 "account": (getattr(from_user, "account", "") or "")
    #             }

    #             requests_list.append({
    #                 "id": req.id,
    #                 "user_id": req.user_id,
    #                 "relation_id": req.relation_id,
    #                 "type": int(getattr(req, "type", 0) or 0),
    #                 # 內層 status 仍保留（避免動到前端），確保是整數
    #                 "status": int(getattr(req, "status", 0) or 0),
    #                 "read": int(getattr(req, "read", 0) or 0),
    #                 "created_at": safe_strftime(getattr(req, "created_at", None)),
    #                 "updated_at": safe_strftime(getattr(req, "updated_at", None)),
    #                 "user": user_info
    #             })

    #         return {"status": "0", "message": "Success",
    #                 "message_code": "SUCCESS", "requests": requests_list}, 200

    #     except Exception as e:
    #         print(f"Get friend requests error: {str(e)}")
    #         return {"status": "1", "message": "Failed to get invitation list",
    #                     "message_code": "GET_INVITATIONS_FAILED"}, 500

        



    @staticmethod
    def add_weight(email: str, weight: float, bmi: float = None, body_fat: float = None, height: float = None, recorded_at: str = None):
        user = User.query.filter_by(email=email).first()
        if not user:
            return {
                "status": "1",
                "message": "User not found",
                "message_code": "USER_NOT_FOUND"
            }, 404

        # 參數型態安全轉換
        try:
            if height is not None:
                height = float(height)
                if height <= 0 or height > 300:
                    return {
                        "status": "1",
                        "message": "Invalid height parameter",
                        "message_code": "INVALID_HEIGHT"
                    }, 400
            else:
                height = 170.0  # 預設值，可依需求調整

            if weight is not None:
                weight = float(weight)
                if weight <= 0 or weight > 500:
                    return {
                        "status": "1",
                        "message": "Invalid weight parameter",
                        "message_code": "INVALID_WEIGHT"
                    }, 400
            else:
                return {
                    "status": "1",
                    "message": "Weight parameter cannot be empty",
                    "message_code": "WEIGHT_REQUIRED"
                }, 400

            if bmi is not None:
                bmi = float(bmi)
                if bmi <= 0 or bmi > 100:
                    return {
                        "status": "1",
                        "message": "Invalid BMI parameter",
                        "message_code": "INVALID_BMI"
                    }, 400
            else:
                bmi = round(weight / ((height / 100) ** 2), 2)

            if body_fat is not None:
                body_fat = float(body_fat)
                if body_fat < 0 or body_fat > 100:
                    return {
                        "status": "1",
                        "message": "Invalid body fat parameter",
                        "message_code": "INVALID_BODY_FAT"
                    }, 400
            else:
                body_fat = 0.0

        except (ValueError, TypeError):
            return {
                "status": "1",
                "message": "Parameter type error",
                "message_code": "PARAMETER_TYPE_ERROR"
            }, 400
        
        if recorded_at:
            try:
                recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                recorded_datetime = recorded_datetime.replace(tzinfo=TZ_TAIWAN)
            except Exception:
                recorded_datetime = datetime.now(TZ_TAIWAN)
        else:
            recorded_datetime = datetime.now(TZ_TAIWAN)
        

        # 新增體重記錄到 Diary
        try:
            new_diary = Diary(
                user_id=user.id,
                weight=weight,
                body_fat=body_fat,
                bmi=bmi,
                type="weight",
                recorded_at=recorded_datetime,
                created_at=datetime.now(TZ_TAIWAN),
                updated_at=datetime.now(TZ_TAIWAN)
            )
            db.session.add(new_diary)
            db.session.commit()
            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "new_record_id": new_diary.id
            }, 200
        except Exception as e:
            print(traceback.format_exc())
            db.session.rollback()
            return {
                "status": "1",
                "message": "Failed to add weight record",
                "message_code": "ADD_WEIGHT_FAILED"
            }, 500
        




    @staticmethod
    def delete_user_records(email: str, delete_ids):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 支援前端傳 dict 格式（如 {"blood_sugars": [23], "weights": [29]}）
            if isinstance(delete_ids, dict):
                merged_ids = []
                for v in delete_ids.values():
                    if isinstance(v, list):
                        merged_ids.extend(v)
                    elif isinstance(v, (str, int)):
                        merged_ids.append(v)
                delete_ids = merged_ids

            # 檢查 delete_ids 必須是 list 且內容都是數字
            if not isinstance(delete_ids, list) or not all(str(i).isdigit() for i in delete_ids):
                return {
                    "status": "1",
                    "message": "deleteObject must be an array of ID numbers",
                    "message_code": "DELETE_OBJECT_MUST_BE_ID_ARRAY"
                }, 400

            # 轉成 int
            delete_ids = [int(i) for i in delete_ids]

            Diary.query.filter(Diary.user_id == user.id, Diary.id.in_(delete_ids)).delete(synchronize_session=False)
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Delete user records error: {str(e)}")
            return {
                "status": "1",
                "message": "Failed to delete health records",
                "message_code": "DELETE_HEALTH_RECORDS_FAILED"
            }, 500
        


    @staticmethod
    def add_diet_record(email: str, description: str, meal: int, tag: list, image: int, lat: float, lng: float, recorded_at: str):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 處理時間
            if recorded_at:
                try:
                    recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    recorded_datetime = recorded_datetime.replace(tzinfo=TZ_TAIWAN)  # 修正
                except Exception:
                    recorded_datetime = datetime.now(TZ_TAIWAN)  # 修正
            else:
                recorded_datetime = datetime.now(TZ_TAIWAN)  # 修正

            # tag 轉成 json 字串
            tag_json = json.dumps(tag, ensure_ascii=False) if isinstance(tag, list) else json.dumps([str(tag)], ensure_ascii=False)

            # location
            location_json = json.dumps({"lat": lat, "lng": lng}, ensure_ascii=False)

            # 新增 Diary 記錄
            new_diary = Diary(
                user_id=user.id,
                description=description,
                meal=meal,
                tag=tag_json,
                image=image,
                location=location_json,
                recorded_at=recorded_datetime,
                type="diet",
                created_at=datetime.now(TZ_TAIWAN),
                updated_at=datetime.now(TZ_TAIWAN)
            )
            db.session.add(new_diary)
            db.session.commit()

            # 假設 image_url 由前端或其他服務產生，這裡先回傳空字串
            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "image_url": ""
            }, 201

        except Exception as e:
            db.session.rollback()
            print(f"Add diet record error: {str(e)}")
            return {
                "status": "1",
                "message": "Failed to add diet record",
                "message_code": "ADD_DIET_FAILED"
            }, 500
        


    @staticmethod
    def add_blood_pressure(email: str, systolic, diastolic, pulse, recorded_at: str = None):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 重新啟用參數驗證 - 這是關鍵修正
            if systolic is None or diastolic is None or pulse is None:
                return {
                    "status": "1",
                    "message": "Blood pressure or heart rate parameters cannot be empty",
                    "message_code": "BP_HR_REQUIRED"
                }, 400

            # 安全的型態轉換，支援字串和數字
            try:
                systolic = int(float(systolic)) if systolic is not None else 0
                diastolic = int(float(diastolic)) if diastolic is not None else 0
                pulse = int(float(pulse)) if pulse is not None else 0
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "Blood pressure and heart rate must be numbers",
                    "message_code": "BP_HR_MUST_BE_NUMBER"
                }, 400

            # 現在可以安全地進行數值比較
            if systolic <= 0 or diastolic <= 0 or pulse <= 0:
                return {
                    "status": "1",
                    "message": "Invalid blood pressure or heart rate values",
                    "message_code": "INVALID_BP_HR"
                }, 400

            # 處理記錄時間
            if recorded_at:
                try:
                    recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    recorded_datetime = recorded_datetime.replace(tzinfo=TZ_TAIWAN)
                except Exception:
                    recorded_datetime = datetime.now(TZ_TAIWAN)
            else:
                recorded_datetime = datetime.now(TZ_TAIWAN)

            # 新增血壓記錄
            new_pressure = Diary(
                user_id=user.id,
                systolic=systolic,
                diastolic=diastolic,
                pulse=pulse,
                type="blood_pressure",
                recorded_at=recorded_datetime,
                created_at=datetime.now(TZ_TAIWAN),
                updated_at=datetime.now(TZ_TAIWAN)
            )
            db.session.add(new_pressure)
            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "records": "成功"
            }, 201

        except Exception as e:
            db.session.rollback()
            print(f"Add blood pressure error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "Failed to add blood pressure record",
                "message_code": "ADD_BLOOD_PRESSURE_FAILED",
                "records": "失敗"
            }, 500
        


    @staticmethod
    def get_friend_invite_code(email: str):
        print("Getting friend invite code...")
        log_memory_usage("Start get_friend_invite_code")
        
        # 確保在 Flask Application Context 中執行
        from flask import has_app_context
        if not has_app_context():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    return AuthController.get_friend_invite_code(email)
            except Exception as context_error:
                print(f"Failed to create app context: {context_error}")
                return {
                    "status": "1",
                    "message": "System error: Unable to create application context",
                    "message_code": "APP_CONTEXT_ERROR"
                }, 500
        
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 檢查 User 表是否已有邀請碼
            if hasattr(user, 'invite_code') and user.invite_code:
                # 如果已經有邀請碼，直接返回
                log_memory_usage("Return existing invite code")
                return {
                    "status": "0",
                    "message": "Success",
                    "message_code": "SUCCESS",
                    "invite_code": user.invite_code
                }, 200

            # 生成固定的邀請碼（基於 user_id 的數學運算）
            user_id_str = f"{user.id:04d}"
            suffix = (user.id * 7 + 1000) % 9000 + 1000
            invite_code = user_id_str + f"{suffix:04d}"
            
            print(f"Generated fixed invite code for user {user.id}: {invite_code}")
            log_memory_usage("Generated invite code")

            # 更安全的資料庫操作
            try:
                # 檢查是否需要更新資料庫
                if hasattr(user, 'invite_code'):
                    if user.invite_code != invite_code:
                        user.invite_code = invite_code
                        # 移除對 updated_at 的引用，因為 User 模型中可能沒有這個欄位
                        
                        # 使用較安全的提交方式
                        db.session.flush()  # 先 flush，檢查是否有錯誤
                        db.session.commit()
                        log_memory_usage("After commit invite code")
                        print(f"Successfully updated invite_code for user {user.id}")
                    else:
                        print(f"Invite code already up to date for user {user.id}")
                else:
                    print(f"User model doesn't have invite_code field, returning generated code")
                    
            except SQLAlchemyError as db_error:
                print(f"Database operation failed: {db_error}")
                db.session.rollback()
                # 即使資料庫更新失敗，仍然返回生成的邀請碼
                print("Continuing with generated invite code despite DB error")
            except Exception as unexpected_error:
                print(f"Unexpected database error: {unexpected_error}")
                try:
                    db.session.rollback()
                except:
                    pass
                print("Continuing with generated invite code despite unexpected error")
            
            log_memory_usage("End get_friend_invite_code")
            return {
                "status": "0",
                "message": "success",
                "message_code": "INVITE_CODE_SUCCESS",
                "invite_code": invite_code
            }, 200

        except Exception as e:
            try:
                db.session.rollback()
            except:
                pass  # 如果 rollback 也失敗，忽略錯誤
            print(f"Get friend invite code error: {str(e)}")
            print(traceback.format_exc())
            log_memory_usage("Error in get_friend_invite_code")
            return {
                "status": "1",
                "message": "failed to get invite code",
                "message_code": "INVITE_CODE_ERROR"
            }, 500
        finally:
            # 強制記憶體清理
            try:
                import gc
                # 清理局部變數
                locals_to_clear = ['user', 'invite_code', 'user_id_str', 'suffix']
                for var_name in locals_to_clear:
                    if var_name in locals():
                        locals()[var_name] = None
                
                # 強制垃圾回收
                collected = gc.collect()
                print(f"GC collected {collected} objects in get_friend_invite_code cleanup")
                
                # 記錄清理後的記憶體狀況
                log_memory_usage("After get_friend_invite_code cleanup")
                
            except Exception as cleanup_error:
                print(f"Cleanup error in get_friend_invite_code: {cleanup_error}")
        


    @staticmethod
    def send_friend_invite(email: str, invite_code: str, relation_type: int):
        print(f"DEBUG: Starting send_friend_invite for user {email}")
        try:
            if not invite_code or not str(invite_code).strip():
                return {"status": "1", "message": "invite code cannot be empty", "message_code": "INVITE_CODE_EMPTY"}, 400

            user = User.query.filter_by(email=email).first()
            if not user:
                return {"status": "1", "message": "user not found", "message_code": "USER_NOT_FOUND"}, 404

            invited_user = User.query.filter_by(invite_code=str(invite_code).strip()).first()
            if not invited_user:
                return {"status": "1", "message": "Please enter a valid friend invite code", "message_code": "INVALID_INVITE_CODE"}, 404

            if user.id == invited_user.id:
                return {"status": "1", "message": "Cannot invite yourself", "message_code": "CANNOT_INVITE_SELF"}, 400
            
            # 檢查雙向是否已是好友或已有待處理邀請
            existing_relation = FriendResult.query.filter(
                db.or_(
                    db.and_(FriendResult.user_id == user.id, FriendResult.relation_id == invited_user.id),
                    db.and_(FriendResult.user_id == invited_user.id, FriendResult.relation_id == user.id)
                ),
                FriendResult.type == relation_type
            ).first()

            if existing_relation:
                if existing_relation.status == 1:
                    return {"status": "1", "message": "Already friends", "message_code": "ALREADY_FRIENDS"}, 409
                elif existing_relation.status == 0:
                    return {"status": "1", "message": "Invitation already sent", "message_code": "INVITATION_ALREADY_SENT"}, 409

            # 🔧 關鍵修復：創建新的邀請記錄
            new_invite = FriendResult(
                user_id=user.id,                # 邀請發送者
                relation_id=invited_user.id,    # 邀請接收者
                type=relation_type,             # 關係類型
                status=0,                       # 待處理
                read=0                          # 未讀
            )
            db.session.add(new_invite)
            db.session.commit()
            
            print(f"DEBUG: Friend invite sent successfully from {user.id} to {invited_user.id}, invite_id={new_invite.id}")
            return {"status": "0", "message": "friend invitation sent successfully", "message_code": "SUCCESS"}, 200

        except Exception as e:
            db.session.rollback()
            print(f"DEBUG: Critical error in send_friend_invite: {str(e)}")
            traceback.print_exc()
            return {"status": "1", "message": "failed to send invitation", "message_code": "SEND_INVITATION_FAILED"}, 500


    @staticmethod
    def find_user_by_invite_code(invite_code):
        """
        根據邀請碼找到對應的使用者
        直接從 User 表中查詢
        """
        try:
            # 嚴格的參數檢查
            if not invite_code:
                print("Invite code is empty")
                return None
                
            invite_code_str = str(invite_code).strip()
            
            # 檢查邀請碼格式
            if len(invite_code_str) != 8:
                print(f"Invalid invite code format: {invite_code_str} (length: {len(invite_code_str)})")
                return None
                
            if not invite_code_str.isdigit():
                print(f"Invalid invite code format: {invite_code_str} (not all digits)")
                return None
            
            print(f"Looking for user with invite code: {invite_code_str}")
            
            # 方法1：如果 User 表有 invite_code 欄位，直接查詢
            try:
                if hasattr(User, 'invite_code'):
                    user = User.query.filter_by(invite_code=invite_code_str).first()
                    if user:
                        print(f"Found user {user.id} via User table")
                        return user
            except Exception as db_error:
                print(f"Database query error in method 1: {db_error}")
            
            # 方法2：解析邀請碼前4位作為 user_id（備用方法）
            try:
                user_id_str = invite_code_str[:4]
                user_id = int(user_id_str)
                
                if user_id <= 0:
                    print(f"Invalid user_id extracted from invite code: {user_id}")
                    return None
                
                user = User.query.filter_by(id=user_id).first()
                if user:
                    # 驗證邀請碼是否正確（使用相同的生成邏輯）
                    try:
                        suffix = (user.id * 7 + 1000) % 9000 + 1000
                        expected_code = f"{user.id:04d}{suffix:04d}"
                        
                        if invite_code_str == expected_code:
                            print(f"Found user {user.id} via code parsing")
                            return user
                        else:
                            print(f"Code mismatch: expected {expected_code}, got {invite_code_str}")
                    except Exception as calc_error:
                        print(f"Error calculating expected code: {calc_error}")
                else:
                    print(f"No user found with ID: {user_id}")
                
            except (ValueError, TypeError) as parse_error:
                print(f"Error parsing user_id from invite code: {parse_error}")
                
            print(f"No user found for invite code: {invite_code_str}")
            return None
            
        except Exception as e:
            print(f"Critical error in find_user_by_invite_code: {str(e)}")
            print(traceback.format_exc())
            return None

    @staticmethod
    def is_already_friend(user_id, target_user_id, relation_type):
        """
        檢查兩個使用者是否已經是指定類型的好友
        應該檢查 FriendResult 表中是否有已接受的邀請
        """
        try:
            # 檢查雙向的已接受邀請
            existing_friendship = FriendResult.query.filter(
                db.or_(
                    db.and_(
                        FriendResult.user_id == user_id,
                        FriendResult.relation_id == target_user_id,
                        FriendResult.type == relation_type,
                        FriendResult.status == 1  # 已接受
                    ),
                    db.and_(
                        FriendResult.user_id == target_user_id,
                        FriendResult.relation_id == user_id,
                        FriendResult.type == relation_type,
                        FriendResult.status == 1  # 已接受
                    )
                )
            ).first()
            
            return existing_friendship is not None
            
        except Exception as e:
            print(f"Is already friend error: {str(e)}")
            return False


    @staticmethod
    def accept_friend_invite(email: str, invite_id: int):
        print(f"========== ACCEPT INVITE START ==========")
        print(f"Invite ID: {invite_id}, User Email: {email}")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                print(f"❌ User not found: {email}")
                return {"status": "1", "message": "User not found", "message_code": "USER_NOT_FOUND"}, 404

            print(f"✅ User found: ID={user.id}, Email={user.email}")

            # 🔧 先查詢邀請是否存在(不限制status)
            invite = FriendResult.query.filter_by(
                id=invite_id,
                relation_id=user.id
            ).first()

            if not invite:
                print(f"❌ Invitation not found: invite_id={invite_id}, relation_id={user.id}")
                return {"status": "1", "message": "Invitation not found", "message_code": "INVITATION_NOT_FOUND"}, 404
            
            print(f"✅ Invitation found: ID={invite.id}, Status={invite.status}, From User={invite.user_id}, To User={invite.relation_id}")
            
            # 🔧 檢查邀請狀態
            if invite.status == 1:
                # 已經接受過了,直接返回成功(冪等性)
                print(f"⚠️ Invitation already accepted (status=1)")
                return {"status": "0", "message": "Friend invitation already accepted", "message_code": "ALREADY_ACCEPTED"}, 200
            elif invite.status == 2:
                # 已經拒絕過了
                print(f"⚠️ Invitation was already rejected (status=2)")
                return {"status": "1", "message": "Invitation was already rejected", "message_code": "ALREADY_REJECTED"}, 400
            
            print(f"✅ Invitation status=0 (pending), proceeding to accept...")
            
            # status=0,待處理的邀請,可以接受
            # 更新邀請狀態為接受
            invite.status = 1
            invite.read = 1
            invite.updated_at = datetime.now(TZ_TAIWAN)
            print(f"✅ Updated invite status to 1 (accepted)")
            
            # 🔧 檢查反向好友關係是否已存在(避免重複創建)
            existing_reverse = FriendResult.query.filter_by(
                user_id=user.id,
                relation_id=invite.user_id
            ).first()
            
            if existing_reverse:
                print(f"⚠️ Reverse friendship already exists: ID={existing_reverse.id}, Status={existing_reverse.status}")
            else:
                print(f"✅ Creating reverse friendship: user_id={user.id} -> relation_id={invite.user_id}")
                # (可選但建議) 為了方便雙向查詢，可以建立一筆反向的已接受紀錄
                # 這能簡化後續查詢好友列表的邏輯
                reverse_friendship = FriendResult(
                    user_id=user.id,
                    relation_id=invite.user_id,
                    type=invite.type,
                    status=1,  # 直接設為已接受
                    read=1,
                    created_at=datetime.now(TZ_TAIWAN),
                    updated_at=datetime.now(TZ_TAIWAN)
                )
                db.session.add(reverse_friendship)
                print(f"✅ Reverse friendship added to session")
            
            db.session.commit()
            print(f"✅ Database commit successful")
            print(f"========== ACCEPT INVITE SUCCESS ==========")
            return {"status": "0", "message": "Friend invitation accepted successfully", "message_code": "SUCCESS"}, 200

        except Exception as e:
            db.session.rollback()
            print(f"❌ Accept friend invite error: {str(e)}")
            traceback.print_exc()
            print(f"========== ACCEPT INVITE FAILED ==========")
            return {"status": "1", "message": "Failed to accept invitation", "message_code": "ACCEPT_INVITATION_FAILED"}, 500


    @staticmethod
    def refuse_friend_invite(email: str, invite_id: int):
        print(f"Refusing friend invite {invite_id} for user {email}")
        log_memory_usage("Start refuse_friend_invite")
        
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1", 
                    "message": "User not found", 
                    "message_code": "USER_NOT_FOUND"
                }, 404

            invite = FriendResult.query.filter_by(
                id=invite_id,
                relation_id=user.id,
                status=0
            ).first()

            if not invite:
                return {
                    "status": "1", 
                    "message": "Invitation not found or already processed", 
                    "message_code": "INVITATION_NOT_FOUND"
                }, 404

            # 🔧 改進：更新邀請狀態為拒絕並標記為已讀
            invite.status = 2
            invite.read = 1  # 標記為已讀
            invite.updated_at = datetime.now(TZ_TAIWAN)
            
            db.session.commit()
            
            log_memory_usage("End refuse_friend_invite")
            return {
                "status": "0", 
                "message": "Invitation rejected successfully", 
                "message_code": "SUCCESS"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Refuse friend invite error: {str(e)}")
            log_memory_usage("Error in refuse_friend_invite")
            return {
                "status": "1", 
                "message": "Failed to refuse invitation", 
                "message_code": "REFUSE_INVITATION_FAILED"
            }, 500
        
        finally:
            # 🔧 添加資源清理
            try:
                db.session.close()
                gc.collect()
                log_memory_usage("After refuse_friend_invite cleanup")
            except:
                pass


    @staticmethod
    def mark_friend_result_as_read(email: str, result_id: int):
        """
        標記邀請結果為已讀
        用於邀請發送者查看對方接受/拒絕的結果後,標記為已讀
        這樣 get_friend_results 就不會再返回這條記錄
        """
        print(f"Marking friend result {result_id} as read for user {email}")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1", 
                    "message": "User not found", 
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 查詢這條邀請結果(必須是我發出的邀請)
            result = FriendResult.query.filter_by(
                id=result_id,
                user_id=user.id  # 確保是我發出的邀請
            ).first()

            if not result:
                return {
                    "status": "1", 
                    "message": "Friend result not found", 
                    "message_code": "RESULT_NOT_FOUND"
                }, 404

            # 標記為已讀
            result.read = 1
            result.updated_at = datetime.now(TZ_TAIWAN)
            
            db.session.commit()
            
            print(f"✅ Friend result {result_id} marked as read")
            return {
                "status": "0", 
                "message": "Friend result marked as read", 
                "message_code": "SUCCESS"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Mark friend result as read error: {str(e)}")
            traceback.print_exc()
            return {
                "status": "1", 
                "message": "Failed to mark result as read", 
                "message_code": "MARK_READ_FAILED"
            }, 500


    @staticmethod
    def remove_friends(email: str, friend_ids: list):
        """
        刪除多個好友
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 驗證參數
            if not isinstance(friend_ids, list) or not friend_ids:
                return {
                    "status": "1",
                    "message": "Please provide friend ID to remove",
                    "message_code": "FRIEND_ID_REQUIRED"
                }, 400

            # 轉換為整數
            try:
                friend_ids = [int(fid) for fid in friend_ids]
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "Invalid friend ID format",
                    "message_code": "INVALID_FRIEND_ID"
                }, 400

            # 刪除好友記錄
            deleted_count = Friend.query.filter(
                Friend.user_id == user.id,
                Friend.id.in_(friend_ids)
            ).delete(synchronize_session=False)

            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Remove friends error: {str(e)}")
            return {
                "status": "1",
                "message": "Failed to remove friend",
                "message_code": "REMOVE_FRIEND_FAILED"
            }, 500
        









    # 添加調試方法到 AuthController
    @staticmethod
    def debug_user_friends(email: str):
        """
        調試用：檢查用戶的好友關係
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            friends = Friend.query.filter_by(user_id=user.id).all()
            friend_data = []
            
            for friend in friends:
                # 安全處理好友名稱
                safe_name = "Friend"
                if friend.name:
                    try:
                        friend.name.encode('ascii')
                        safe_name = friend.name
                    except UnicodeEncodeError:
                        # 如果包含中文，轉換為安全的名稱
                        relation_map = {0: "Doctor Group", 1: "Family Group", 2: "Control Group"}
                        safe_name = relation_map.get(friend.relation_type, f"Group{friend.relation_type}")
                
                friend_data.append({
                    "id": friend.id,
                    "name": safe_name,
                    "relation_type": friend.relation_type,
                    "created_at": friend.created_at.strftime("%Y-%m-%d %H:%M:%S") if friend.created_at else None
                })

            return {
                "user_id": user.id,
                "total_friends": len(friends),
                "friends": friend_data,
                "by_type": {
                    "doctor_group(0)": len([f for f in friends if f.relation_type == 0]),
                    "family_group(1)": len([f for f in friends if f.relation_type == 1]),
                    "control_group(2)": len([f for f in friends if f.relation_type == 2])
                }
            }, 200

        except Exception as e:
            return {
                "error": f"Debug error: {str(e)}",
                "message_code": "DEBUG_ERROR"
            }, 500
        


    @staticmethod
    def create_default_friends_for_user(email: str):
        """
        為現有用戶創建預設好友關係
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "User not found",
                    "message_code": "USER_NOT_FOUND"
                }, 404

            # 檢查是否已有預設好友
            existing_friends = Friend.query.filter_by(user_id=user.id).all()
            existing_types = [f.relation_type for f in existing_friends]

            # 預設好友列表
            default_friends = [
                {"name": "醫師團", "relation_type": 0},
                {"name": "親友團", "relation_type": 1}, 
                {"name": "控糖團", "relation_type": 2}
            ]

            added_friends = []
            for friend_data in default_friends:
                # 只添加不存在的關係類型
                if friend_data["relation_type"] not in existing_types:
                    default_friend = Friend(
                        user_id=user.id,
                        name=friend_data["name"],
                        relation_type=friend_data["relation_type"],
                        created_at=datetime.now(TZ_TAIWAN),
                        updated_at=datetime.now(TZ_TAIWAN)
                    )
                    db.session.add(default_friend)
                    added_friends.append(friend_data["name"])

            db.session.commit()

            return {
                "status": "0",
                "message": "Success",
                "message_code": "SUCCESS",
                "added_friends": added_friends
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Create default friends error: {str(e)}")
            return {
                "status": "1",
                "message": "Failed to create default friends",
                "message_code": "CREATE_DEFAULT_FRIENDS_FAILED"
            }, 500
