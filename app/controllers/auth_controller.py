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
import hashlib
import time


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
                    "message": "email 格式不正確"
                }, 400

            # 驗證密碼長度
            if len(password) < 8:
                return {
                    "status": "1",
                    "message": "密碼至少需要 8 個字元"
                }, 400

            # 檢查 email 是否已存在
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                if existing_user.is_verified:
                    return {
                        "status": "1",
                        "message": "此 email 已被註冊且已驗證"
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
                                "message": "此帳號已被使用"
                            }, 409
                
                    # 更新密碼和帳號
                    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
                    existing_user.password_hash = pw_hash
                    if account:
                        existing_user.account = account
                
                    # 生成新的驗證碼
                    verification_code = str(random.randint(100000, 999999))
                    existing_user.verification_code = verification_code
                    existing_user.verification_code_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
                    
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
                    "message": "註冊成功，驗證碼已發送至您的信箱",
                    "needs_verification": True
                }, 200
        
            # 檢查 account 是否已存在（如果有提供）
            if account and User.query.filter_by(account=account).first():
                return {
                    "status": "1",
                    "message": "此帳號已被使用"
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
                    verification_code_expires=datetime.now(timezone.utc) + timedelta(minutes=15)
                )
                db.session.add(user)
                db.session.flush()  # 先 flush 以取得 user.id
                
                # 為新使用者建立預設好友
                default_friends = [
                    {"name": "系統管理員", "relation_type": 0},
                    {"name": "醫療諮詢", "relation_type": 1},
                    {"name": "糖友互助", "relation_type": 2}
                ]
                
                for friend_data in default_friends:
                    default_friend = Friend(
                        user_id=user.id,
                        name=friend_data["name"],
                        relation_type=friend_data["relation_type"],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
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
                    "message": "註冊成功，驗證碼已發送至您的信箱",
                    "needs_verification": True
                }, 201
        
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "註冊失敗"
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
                    "message": "email 不能為空"
                }, 400
                
            if not EMAIL_RE.match(email):
                return {
                    "status": "1",
                    "message": "email 格式不正確"
                }, 400
            
            # 檢查 email 是否已經註冊
            existing_user = User.query.filter_by(email=email).first()
            
            if existing_user:
                # 如果已驗證，不允許重複註冊
                if existing_user.is_verified:
                    return {
                        "status": "1",
                        "message": "此 email 已被註冊且已驗證"
                    }, 409
                else:
                    # 如果未驗證，自動發送驗證碼
                    verification_code = str(random.randint(100000, 999999))
                    existing_user.verification_code = verification_code
                    existing_user.verification_code_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
                    
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
                    "message": "此 email 已註冊但未驗證，驗證碼已重新發送",
                    "user_exists": True,
                    "needs_verification": True
                }, 200
    
            return {
                "status": "0",
                "message": "email 可以使用",
                "user_exists": False
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "檢查失敗"
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
                    "message": "email 格式不正確"
                }, 400
            
            # 檢查密碼是否為空
            if not password:
                return {
                    "status": "1",
                    "message": "密碼不能為空"
                }, 400

            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            
            # 驗證使用者存在且密碼正確
            if not user or not bcrypt.check_password_hash(user.password_hash, password):
                return {
                    "status": "1",
                    "message": "帳號或密碼錯誤"
                }, 401

            # 建立 JWT，使用 email 作為 identity
            token = create_access_token(identity=email)
            
            return {
                "status": "0",
                "message": "登入成功",
                "token": token
            }, 200
    
        except Exception as e:
            return {
                "status": "1",
                "message": "登入失敗"
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
                    "message": "此 email 未註冊"
                }, 404
            
            # 生成新的驗證碼
            verification_code = str(random.randint(100000, 999999))
            user.verification_code = verification_code
            user.verification_code_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
            
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
                "message": "驗證碼已發送"
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "發送失敗"
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
                    "message": "使用者不存在"
                }, 404
            
            # 檢查驗證碼
            if user.verification_code != code:
                return {
                    "status": "1",
                    "message": "驗證碼錯誤"
                }, 400
            
            # 檢查驗證碼是否過期
            print(user.verification_code_expires)
            print(type(user.verification_code_expires))

            print(datetime.now() + timedelta(hours=8))
            print(type(datetime.now()))
            if user.verification_code_expires + timedelta(hours=8) and user.verification_code_expires + timedelta(hours=8) < datetime.now():
                return {
                    "status": "1",
                    "message": "驗證碼已過期"
                }, 400
            
            # 驗證成功，標記為已驗證
            user.is_verified = True
            user.verification_code = None
            user.verification_code_expires = None
            
            db.session.commit()
            
            return {
                "status": "0",
                "message": "驗證成功"
            }, 200
            
        except Exception as e:
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "驗證失敗"
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
                    "message": "email 格式不正確"
                }, 400
            
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "此 email 未註冊"
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
                "message": "新密碼已發送至您的 email",
                "temp_password": new_password  # 僅供測試，正式環境應移除
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "重設失敗"
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
                    "message": "密碼至少需要 8 個字元"
                }, 400
            
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404
            
            # 更新密碼
            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
            user.must_change_password = 0  # 清除必須重設密碼標記
            
            db.session.commit()
            
            return {
                "status": "0",
                "message": "密碼重設成功"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "重設失敗"
            }, 500

    @staticmethod
    def get_user(email: str):
        print("Getting user info...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 安全地查詢相關健康資料
            user_default = None
            user_setting = None
            user_vip = None
            user_a1c = None  # 新增：查詢使用者的 A1c 記錄
            
            try:
                user_default = UserDefault.query.filter_by(user_id=user.id).first()
            except Exception as e:
                user_default = None

            try:
                user_setting = UserSetting.query.filter_by(user_id=user.id).first()
            except Exception as e:
                user_setting = None

            try:
                user_vip = UserVip.query.filter_by(user_id=user.id).first()
            except Exception as e:
                user_vip = None

            # 新增：查詢使用者最新的 A1c 記錄
            try:
                user_a1c = A1cRecord.query.filter_by(user_id=user.id).order_by(A1cRecord.created_at.desc()).first()
            except Exception as e:
                user_a1c = None

            # 安全處理 gender 轉換
            try:
                gender_value = 0
                if hasattr(user, 'gender') and user.gender is not None:
                    gender_value = 1 if user.gender else 0
            except Exception as e:
                gender_value = 0

            # 安全的字串格式化函數
            def safe_strftime(dt, format_str="%Y-%m-%d %H:%M:%S", default=""):
                if not dt:
                    return default
                try:
                    return dt.strftime(format_str)
                except Exception as e:
                    return default

            # 安全的屬性取得函數
            def safe_getattr(obj, attr, default=None):
                if not obj:
                    return default
                try:
                    value = getattr(obj, attr, default)
                    return value if value is not None else default
                except Exception as e:
                    return default

            # 安全的浮點數轉換
            def safe_float(value, default=0.0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError) as e:
                    return default

            # 建構回應資料
            response_data = {
                "status": "0",
                "message": "成功",
                "user": {
                    "status": "0",
                    "id": int(user.id),
                    "name": safe_getattr(user, 'name', ''),
                    "account": safe_getattr(user, 'account', ''),
                    "email": user.email,
                    "phone": safe_getattr(user, 'phone', ''),
                    "fb_id": safe_getattr(user, 'fb_id', '未設置'),
                    "status": safe_getattr(user, 'status', 'Normal'),
                    "group": safe_getattr(user, 'group', '0'),
                    "birthday": safe_getattr(user, 'birthday', ''),
                    "height": safe_float(safe_getattr(user, 'height')),
                    "weight": safe_float(safe_getattr(user, 'weight')),
                    "gender": gender_value,
                    "address": safe_getattr(user, 'address', ''),
                    "unread_records": [0, 0, 0],
                    "verified": 1 if safe_getattr(user, 'is_verified', False) else 0,
                    "privacy_policy": 1,
                    "must_change_password": safe_getattr(user, 'must_change_password', 0),
                    "fcm_id": safe_getattr(user, 'fcm_id', ''),
                    "login_times": 0,
                    "created_at": safe_strftime(safe_getattr(user, 'created_at')),
                    "updated_at": safe_strftime(safe_getattr(user, 'created_at')),
                    
                    # 健康預設值
                    "default": {
                        "id": safe_getattr(user_default, 'id', 1),
                        "user_id": user.id,
                        "sugar_delta_max": safe_float(safe_getattr(user_default, 'sugar_delta_max')),
                        "sugar_delta_min": safe_float(safe_getattr(user_default, 'sugar_delta_min')),
                        "sugar_morning_max": safe_float(safe_getattr(user_default, 'sugar_morning_max')),
                        "sugar_morning_min": safe_float(safe_getattr(user_default, 'sugar_morning_min')),
                        "sugar_evening_max": safe_float(safe_getattr(user_default, 'sugar_evening_max')),
                        "sugar_evening_min": safe_float(safe_getattr(user_default, 'sugar_evening_min')),
                        "sugar_before_max": safe_float(safe_getattr(user_default, 'sugar_before_max')),
                        "sugar_before_min": safe_float(safe_getattr(user_default, 'sugar_before_min')),
                        "sugar_after_max": safe_float(safe_getattr(user_default, 'sugar_after_max')),
                        "sugar_after_min": safe_float(safe_getattr(user_default, 'sugar_after_min')),
                        "systolic_max": safe_getattr(user_default, 'systolic_max', 0),
                        "systolic_min": safe_getattr(user_default, 'systolic_min', 0),
                        "diastolic_max": safe_getattr(user_default, 'diastolic_max', 0),
                        "diastolic_min": safe_getattr(user_default, 'diastolic_min', 0),
                        "pulse_max": safe_getattr(user_default, 'pulse_max', 0),
                        "pulse_min": safe_getattr(user_default, 'pulse_min', 0),
                        "weight_max": safe_float(safe_getattr(user_default, 'weight_max')),
                        "weight_min": safe_float(safe_getattr(user_default, 'weight_min')),
                        "bmi_max": safe_float(safe_getattr(user_default, 'bmi_max')),
                        "bmi_min": safe_float(safe_getattr(user_default, 'bmi_min')),
                        "body_fat_max": safe_float(safe_getattr(user_default, 'body_fat_max')),
                        "body_fat_min": safe_float(safe_getattr(user_default, 'body_fat_min')),
                        "created_at": safe_strftime(safe_getattr(user_default, 'created_at'), default="2023-08-23 16:51:14"),
                        "updated_at": safe_strftime(safe_getattr(user_default, 'updated_at'), default="2023-08-23 16:51:14")
                    },
                    
                    # 使用者設定
                    "setting": {
                        "id": safe_getattr(user_setting, 'id', 1),
                        "user_id": user.id,
                        "after_recording": safe_getattr(user_setting, 'after_recording', 0),
                        "no_recording_for_a_day": safe_getattr(user_setting, 'no_recording_for_a_day', 0),
                        "over_max_or_under_min": safe_getattr(user_setting, 'over_max_or_under_min', 0),
                        "after_meal": safe_getattr(user_setting, 'after_meal', 0),
                        "unit_of_sugar": safe_getattr(user_setting, 'unit_of_sugar', 0),
                        "unit_of_weight": safe_getattr(user_setting, 'unit_of_weight', 0),
                        "unit_of_height": safe_getattr(user_setting, 'unit_of_height', 0),
                        "created_at": safe_strftime(safe_getattr(user_setting, 'created_at'), default="2023-02-03 08:17:17"),
                        "updated_at": safe_strftime(safe_getattr(user_setting, 'updated_at'), default="2023-02-03 08:17:17")
                    },
                    
                    # VIP 資訊
                    "vip": {
                        "id": safe_getattr(user_vip, 'id', 1),
                        "user_id": user.id,
                        "level": safe_getattr(user_vip, 'level', 0),
                        "remark": safe_float(safe_getattr(user_vip, 'remark')),
                        "started_at": safe_getattr(user_vip, 'started_at', "2023-02-03 08:17:17"),
                        "ended_at": safe_getattr(user_vip, 'ended_at', "2023-02-03 08:17:17"),
                        "created_at": safe_strftime(safe_getattr(user_vip, 'created_at'), default="2023-02-03 08:17:17"),
                        "updated_at": safe_strftime(safe_getattr(user_vip, 'updated_at'), default="2023-02-03 08:17:17")
                    },
                    "a1c": {
                        "message": safe_getattr(user_a1c, 'message', "") if user_a1c else "",
                        "latest_value": safe_getattr(user_a1c, 'A1c', 0.0) if user_a1c else 0.0,
                        "latest_date": safe_strftime(safe_getattr(user_a1c, 'record_date')) if user_a1c else ""
                    }
                }
            }

            return response_data, 200

        except Exception as e:
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "取得使用者資訊失敗"
            }, 500

    @staticmethod
    def update_user(email: str, user_data: dict):
        print("Updating user...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
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
                                "message": "此 email 已被使用"
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
                                "message": "此帳號已被使用"
                            }, 409
                        user.account = new_account

            # 最終安全檢查 - 確保 email 絕對不會是空的
            if not user.email or user.email.strip() == '':
                user.email = original_email
            
            # 儲存到資料庫
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "更新失敗"
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
                    "message": "使用者不存在"
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
            user_setting.updated_at = datetime.now(timezone.utc)
            
            # 儲存到資料庫
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200
            
        except Exception as e:  
            db.session.rollback()
            return {
                "status": "1",
                "message": "更新設定失敗"
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
                    "message": "使用者不存在"
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
                "message": "成功",
                "medical_info": medical_info
            }, 200
    
        except Exception as e:
            return {
                "status": "1",
                "message": "取得病歷失敗"
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
                    "message": "使用者不存在"
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
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
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
            user_medical.updated_at = datetime.now(timezone.utc)
            
            # 儲存到資料庫
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "更新病歷失敗"
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
                    "message": "使用者不存在"
                }, 404
            
            # 驗證 A1c 值
            if a1c_value <= 0 or a1c_value > 20:
                return {
                    "status": "1",
                    "message": "HbA1c 值無效"
                }, 400
            
            # 解析日期
            try:
                record_date_parsed = datetime.strptime(record_date, "%Y-%m-%d").date()
            except ValueError:
                return {
                    "status": "1",
                    "message": "日期格式錯誤，應為 YYYY-MM-DD"
                }, 400
            
            # 檢查是否已有相同日期的記錄
            existing_record = A1cRecord.query.filter_by(
                user_id=user.id,
                record_date=record_date_parsed
            ).first()
            
            if existing_record:
                # 更新現有記錄
                existing_record.A1c = a1c_value
                existing_record.updated_at = datetime.now(timezone.utc)
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
                "message": "成功"
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "新增 HbA1c 記錄失敗"
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
                    "message": "使用者不存在"
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
                "message": "成功",
                "a1cs": records_list  
            }, 200
            
        except Exception as e:
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "取得 HbA1c 記錄失敗"
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
                    "message": "使用者不存在"
                }, 404
            
            # 驗證 care_data
            if not care_data or not care_data.strip():
                return {
                    "status": "1",
                    "message": "care_data 不能為空"
                }, 400

            # 檢查是否已有相同的照護紀錄
            existing_record = A1cRecord.query.filter_by(
                user_id=user.id,
                care_data=care_data.strip()
            ).first()

            if existing_record:
                existing_record.updated_at = datetime.now(timezone.utc)
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
                "message": "成功",
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "新增 Care 記錄失敗"
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
                    "message": "使用者不存在"
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
                "message": "成功",
                "cares": records_list
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "取得 Care 記錄失敗"
            }, 500

    



    @staticmethod
    def add_share_record(email: str, record_type: int, record_id: int, relation_type: int):
        print("Adding share record...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404
            
            # 驗證輸入參數
            if record_type not in [0, 1, 2, 3]:
                return {
                    "status": "1",
                    "message": "type 參數無效"
                }, 400

            if relation_type not in [0, 1, 2]:
                return {
                    "status": "1",
                    "message": "relation_type 參數無效"
                }, 400
                
            if not record_id or record_id <= 0:
                return {
                    "status": "1",
                    "message": "record_id 參數無效"
                }, 400
            
            # 新增：檢查使用者是否有對應類型的好友
            if not AuthController.has_friend_in_relation(user.id, relation_type):
                relation_names = {0: "醫師團", 1: "親友團", 2: "糖友團"}
                return {
                    "status": "1",
                    "message": f"您尚未加入{relation_names.get(relation_type, '該')}，請先新增好友"
                }, 400
            
            # 檢查是否已經分享過相同記錄
            existing_share = ShareRecord.query.filter_by(
                user_id=user.id,
                record_type=record_type,
                record_id=record_id,
                relation_type=relation_type
            ).first()
            
            if existing_share:
                # 更新分享時間
                existing_share.shared_at = datetime.now(timezone.utc)
            else:
                # 建立新的分享記錄
                new_share = ShareRecord(
                    user_id=user.id,
                    record_type=record_type,
                    record_id=record_id,
                    relation_type=relation_type,
                    shared_at=datetime.now(timezone.utc)
                )
                db.session.add(new_share)
            
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200
            
        except Exception as e:
            print(f"add_share_record error: {str(e)}")
            db.session.rollback()
            return {
                "status": "1",
                "message": "分享失敗"
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
        print(f"Getting shared records for email: {email}, relation_type: {relation_type}")
        
        try:
            # 1) 基本檢查
            user = User.query.filter_by(email=email).first()
            if not user:
                print(f"User not found for email: {email}")
                return {"status": "1", "message": "使用者不存在"}, 404

            print(f"Found user: {user.id}")

            # 參數驗證 - 處理路徑參數(字串類型)
            # 前端對應: 醫師團=0, 親友團=1, 控糖團=2
            print(f"Original relation_type: {relation_type}, type: {type(relation_type)}")
            
            try:
                # 路徑參數都是字串，需要轉換
                if isinstance(relation_type, str):
                    relation_type = relation_type.strip()
                    print(f"Stripped relation_type: '{relation_type}'")
                    
                    # 檢查是否為數字字串
                    if not relation_type.isdigit():
                        print(f"relation_type is not digit: '{relation_type}'")
                        return {"status": "1", "message": "type 參數格式錯誤"}, 400
                        
                    relation_type_int = int(relation_type)
                elif isinstance(relation_type, int):
                    relation_type_int = relation_type
                else:
                    print(f"Unexpected relation_type type: {type(relation_type)}")
                    return {"status": "1", "message": "type 參數格式錯誤"}, 400
                    
            except (ValueError, TypeError) as e:
                print(f"Parameter conversion error: {e}")
                return {"status": "1", "message": "type 參數格式錯誤"}, 400

            print(f"Converted relation_type_int: {relation_type_int}")

            if relation_type_int not in (0, 1, 2):
                print(f"Invalid relation_type_int: {relation_type_int}")
                return {"status": "1", "message": "type 參數無效"}, 400

            # 對應關係確認
            type_names = {0: "醫師團", 1: "親友團", 2: "控糖團"}
            print(f"Requesting records for: {type_names.get(relation_type_int, 'Unknown')}")

            # 2) 查詢分享記錄
            try:
                print(f"Querying ShareRecord table for user_id: {user.id}")
                
                print(f"Querying share records for user with relation_type: {relation_type_int} ({type_names.get(relation_type_int)})")
                share_records = ShareRecord.query.filter_by(
                    user_id=user.id, 
                    relation_type=relation_type_int
                ).all()
                
                print(f"Found {len(share_records)} share records")
                
                # 如果沒有找到記錄，輸出更多調試信息
                if len(share_records) == 0:
                    print("No share records found, checking total records for this user...")
                    all_user_shares = ShareRecord.query.filter_by(user_id=user.id).all()
                    print(f"User has {len(all_user_shares)} total share records")
                    for share in all_user_shares:
                        print(f"  Share ID: {share.id}, relation_type: {getattr(share, 'relation_type', 'None')}")
                
            except Exception as e:
                print(f"Database query error in ShareRecord: {str(e)}")
                import traceback
                traceback.print_exc()
                return {"status": "1", "message": "查詢資料失敗"}, 500

            # 統一使用 timezone.utc
            tz_utc = timezone.utc
            records_list = []

            for i, share in enumerate(share_records):
                print(f"Processing share record {i+1}/{len(share_records)}: ID={share.id}, record_id={getattr(share, 'record_id', 'None')}")
                
                try:
                    # 檢查必要屬性
                    if not hasattr(share, 'record_id') or share.record_id is None:
                        print(f"Share record {share.id} has invalid record_id: {getattr(share, 'record_id', 'None')}")
                        continue

                    # 檢查 record_type 確保查詢正確的表
                    share_record_type = getattr(share, 'record_type', None)
                    print(f"Share record_type: {share_record_type}")
                    
                    # 根據 record_type 決定查詢哪個表
                    # 假設: 0=日記, 1=血壓, 2=血糖, 3=其他
                    diary = None
                    try:
                        print(f"Querying diary with id: {share.record_id}")
                        
                        # 這裡需要根據您的實際數據庫結構調整
                        # 如果不同 record_type 對應不同的表，請修改這裡
                        diary = Diary.query.filter_by(id=share.record_id).first()
                        
                        if diary:
                            print(f"Found diary record: {diary.id}")
                        else:
                            print(f"No diary found for record_id: {share.record_id}")
                            # 檢查記錄是否存在於其他表中
                            print(f"Checking if record_id {share.record_id} exists in database...")
                            
                    except Exception as e:
                        print(f"Diary query error for record_id {share.record_id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue

                    # 安全轉換函數
                    def safe_int(value, default=0, field_name=""):
                        try:
                            if value is None:
                                return default
                            if isinstance(value, str) and value.strip() == "":
                                return default
                            result = int(float(value))
                            return result
                        except (ValueError, TypeError) as e:
                            if field_name:
                                print(f"safe_int conversion error for {field_name} '{value}': {e}")
                            return default

                    def safe_float(value, default=0.0, field_name=""):
                        try:
                            if value is None:
                                return default
                            if isinstance(value, str) and value.strip() == "":
                                return default
                            result = float(value)
                            return result
                        except (ValueError, TypeError) as e:
                            if field_name:
                                print(f"safe_float conversion error for {field_name} '{value}': {e}")
                            return default

                    def safe_str(value, default="", field_name=""):
                        try:
                            if value is None:
                                return default
                            return str(value)
                        except Exception as e:
                            if field_name:
                                print(f"safe_str conversion error for {field_name} '{value}': {e}")
                            return default

                    # 基本數值欄位
                    systolic = safe_int(getattr(diary, "systolic", 0) if diary else 0, 0, "systolic")
                    diastolic = safe_int(getattr(diary, "diastolic", 0) if diary else 0, 0, "diastolic")
                    bmi = safe_int(getattr(diary, "bmi", 0) if diary else 0, 0, "bmi")
                    pulse = safe_int(getattr(diary, "pulse", 0) if diary else 0, 0, "pulse")
                    meal = safe_int(getattr(diary, "meal", 0) if diary else 0, 0, "meal")
                    weight = safe_float(getattr(diary, "weight", 0.0) if diary else 0.0, 0.0, "weight")
                    body_fat = safe_float(getattr(diary, "body_fat", 0.0) if diary else 0.0, 0.0, "body_fat")
                    sugar = safe_float(getattr(diary, "sugar", 0.0) if diary else 0.0, 0.0, "sugar")

                    print(f"Processed basic numeric fields for record {share.id}")

                    # 複雜欄位處理 - tag
                    tag_2d = [[]]
                    try:
                        tag_raw = getattr(diary, "tag", None) if diary else None
                        print(f"Processing tag_raw: {type(tag_raw)}, value preview: {str(tag_raw)[:100] if tag_raw else 'None'}")
                        
                        if tag_raw is not None:
                            if isinstance(tag_raw, list):
                                rows = []
                                for item in tag_raw:
                                    if isinstance(item, list):
                                        rows.append([safe_str(x, "", f"tag_item") for x in item])
                                    elif isinstance(item, dict):
                                        names = item.get("name") if "name" in item else None
                                        if isinstance(names, list):
                                            rows.append([safe_str(x, "", f"tag_name") for x in names])
                                        else:
                                            rows.append([])
                                    else:
                                        # 單個值也轉為列表
                                        rows.append([safe_str(item, "", "tag_single")])
                                tag_2d = rows if rows else [[]]
                            elif isinstance(tag_raw, dict):
                                names = tag_raw.get("name")
                                if isinstance(names, list):
                                    tag_2d = [[safe_str(x, "", "tag_dict_name") for x in names]]
                                else:
                                    tag_2d = [[safe_str(names, "", "tag_dict_single")] if names else []]
                            elif isinstance(tag_raw, str):
                                # 字串可能是 JSON 格式，嘗試解析
                                try:
                                    import json
                                    parsed = json.loads(tag_raw)
                                    if isinstance(parsed, list):
                                        tag_2d = [[safe_str(x, "", "tag_json") for x in parsed]]
                                    else:
                                        tag_2d = [[safe_str(tag_raw, "", "tag_str")]]
                                except:
                                    tag_2d = [[safe_str(tag_raw, "", "tag_str_fallback")]]
                            else:
                                tag_2d = [[safe_str(tag_raw, "", "tag_other")]]
                                
                    except Exception as e:
                        print(f"Tag processing error for record {share.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        tag_2d = [[]]

                    # 複雜欄位處理 - image
                    image_1d = []
                    try:
                        image_raw = getattr(diary, "image", None) if diary else None
                        print(f"Processing image_raw: {type(image_raw)}")
                        
                        if image_raw is not None:
                            if isinstance(image_raw, list):
                                image_1d = [safe_str(x, "", "image_item") for x in image_raw if x is not None]
                            elif isinstance(image_raw, str):
                                if image_raw.strip():
                                    # 可能是 JSON 字串
                                    try:
                                        import json
                                        parsed = json.loads(image_raw)
                                        if isinstance(parsed, list):
                                            image_1d = [safe_str(x, "", "image_json") for x in parsed if x is not None]
                                        else:
                                            image_1d = [safe_str(image_raw, "", "image_str")]
                                    except:
                                        image_1d = [safe_str(image_raw, "", "image_str_fallback")]
                            else:
                                image_1d = [safe_str(image_raw, "", "image_other")]
                                
                    except Exception as e:
                        print(f"Image processing error for record {share.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        image_1d = []

                    # 複雜欄位處理 - location
                    location_obj = {"lat": "", "lng": "", "address": ""}
                    try:
                        location_raw = getattr(diary, "location", None) if diary else None
                        print(f"Processing location_raw: {type(location_raw)}")
                        
                        if location_raw is not None:
                            if isinstance(location_raw, dict):
                                lat_val = (location_raw.get("lat") or location_raw.get("latitude") or 
                                        location_raw.get("y") or "")
                                lng_val = (location_raw.get("lng") or location_raw.get("lon") or
                                        location_raw.get("long") or location_raw.get("longitude") or
                                        location_raw.get("x") or "")
                                addr_val = (location_raw.get("address") or location_raw.get("name") or
                                        location_raw.get("text") or location_raw.get("display_name") or "")
                                
                                location_obj = {
                                    "lat": safe_str(lat_val, "", "location_lat"), 
                                    "lng": safe_str(lng_val, "", "location_lng"), 
                                    "address": safe_str(addr_val, "", "location_addr")
                                }
                            elif isinstance(location_raw, list) and len(location_raw) >= 2:
                                location_obj = {
                                    "lat": safe_str(location_raw[0], "", "location_list_lat"), 
                                    "lng": safe_str(location_raw[1], "", "location_list_lng"), 
                                    "address": ""
                                }
                            elif isinstance(location_raw, str):
                                if "," in location_raw:
                                    parts = [p.strip() for p in location_raw.split(",")]
                                    if len(parts) >= 2:
                                        location_obj = {"lat": parts[0], "lng": parts[1], "address": ""}
                                    else:
                                        location_obj = {"lat": "", "lng": "", "address": location_raw}
                                else:
                                    # 可能是 JSON 字串
                                    try:
                                        import json
                                        parsed = json.loads(location_raw)
                                        if isinstance(parsed, dict):
                                            lat_val = (parsed.get("lat") or parsed.get("latitude") or parsed.get("y") or "")
                                            lng_val = (parsed.get("lng") or parsed.get("lon") or parsed.get("longitude") or parsed.get("x") or "")
                                            addr_val = (parsed.get("address") or parsed.get("name") or "")
                                            location_obj = {"lat": safe_str(lat_val), "lng": safe_str(lng_val), "address": safe_str(addr_val)}
                                        else:
                                            location_obj = {"lat": "", "lng": "", "address": safe_str(location_raw)}
                                    except:
                                        location_obj = {"lat": "", "lng": "", "address": safe_str(location_raw)}
                            else:
                                location_obj = {"lat": "", "lng": "", "address": safe_str(location_raw, "", "location_fallback")}
                                
                    except Exception as e:
                        print(f"Location processing error for record {share.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        location_obj = {"lat": "", "lng": "", "address": safe_str(location_raw, "", "location_fallback")}

                    # user 物件
                    user_obj = {
                        "id": user.id,
                        "name": safe_str(user.name, "", "user_name"),
                        "email": safe_str(user.email, "", "user_email"),
                        "account": safe_str(user.account, "", "user_account"),
                    }

                    # 時間處理函數
                    def safe_datetime_to_iso(dt_value, field_name=""):
                        try:
                            if isinstance(dt_value, datetime):
                                if dt_value.tzinfo is None:
                                    dt_value = dt_value.replace(tzinfo=tz_utc)
                                return dt_value.astimezone(tz_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                            elif isinstance(dt_value, (int, float)):
                                return datetime.fromtimestamp(float(dt_value), tz=tz_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                            elif isinstance(dt_value, str):
                                return dt_value.strip() if dt_value else ""
                            else:
                                return ""
                        except Exception as e:
                            print(f"DateTime conversion error for {field_name}: {e}")
                            return ""

                    def safe_datetime_to_string(dt_value, field_name=""):
                        try:
                            if isinstance(dt_value, datetime):
                                return dt_value.strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                return ""
                        except Exception as e:
                            print(f"DateTime string conversion error for {field_name}: {e}")
                            return ""

                    # 時間欄位處理
                    recorded_at = safe_datetime_to_iso(
                        getattr(diary, "recorded_at", None) if diary else None, 
                        "recorded_at"
                    )
                    shared_at = safe_datetime_to_iso(
                        getattr(share, "shared_at", None), 
                        "shared_at"
                    )
                    created_at = safe_datetime_to_string(
                        getattr(diary, "created_at", None) if diary else None, 
                        "created_at"
                    )

                    print(f"Processed datetime fields for record {share.id}")

                    # 組裝最終記錄
                    try:
                        record_data = {
                            "id": share.id,
                            "user_id": share.user_id,
                            "relation_id": safe_int(getattr(share, "relation_id", 0), 0, "relation_id"),
                            "user": user_obj,
                            "type": safe_int(getattr(share, "record_type", 0), 0, "type"),
                            "record_type": safe_int(getattr(share, "record_type", 0), 0, "record_type"),
                            "weight": weight,
                            "body_fat": body_fat,
                            "sugar": sugar,
                            "meal_type": safe_int(getattr(diary, "meal_type", 0) if diary else 0, 0, "meal_type"),
                            "bmi": bmi,
                            "shared_at": shared_at,
                            "recorded_at": recorded_at,
                            "created_at": created_at,
                            "meal": meal,
                            "timeperiod": safe_int(getattr(diary, "timeperiod", 0) if diary else 0, 0, "timeperiod"),
                            "tag": tag_2d,
                            "image": image_1d,
                            "location": location_obj,
                            "relation_type": safe_int(getattr(share, "relation_type", 0), 0, "share_relation_type"),
                            "systolic": systolic,
                            "diastolic": diastolic,
                            "pulse": pulse,
                            "message": safe_str(getattr(diary, "message", "") if diary else "", "", "message"),
                            "url": safe_str(getattr(diary, "url", "") if diary else "", "", "url"),
                            "record_status": safe_int(getattr(diary, "status", 0) if diary else 0, 0, "record_status"),
                        }

                        records_list.append(record_data)
                        print(f"Successfully processed and added record {share.id}")
                        
                    except Exception as e:
                        print(f"Error assembling record data for share {share.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue
                    
                except Exception as e:
                    print(f"Error processing share record {share.id}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue

            print(f"Returning {len(records_list)} processed records out of {len(share_records)} total share records")
            return {"status": "0", "message": "成功", "records": records_list}, 200

        except Exception as e:
            print(f"get_shared_records critical error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"status": "1", "message": "獲取分享記錄失敗"}, 500



    @staticmethod
    def get_news(email: str):
        print("Getting news...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
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
            
                news_data = {
                    "id": news.id,
                    "member_id": news.member_id,
                    "group": news.group,
                    "title": news.title or "",
                    "message": news.message or "",
                    "pushed_at": safe_strftime(news.pushed_at),
                    "created_at": safe_strftime(news.created_at),
                    "updated_at": safe_strftime(news.updated_at)
                }
                
                news_list.append(news_data)

            return {
                "status": "0",
                "message": "成功",
                "news": news_list
            }, 200
            
        except Exception as e:
            return {
                "status": "1",
                "message": "取得最新消息失敗"
            }, 500
        


    @staticmethod
    def get_friend_list(email: str):
        print("Getting friend list...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404
            
            # 查詢使用者的好友列表
            friends = Friend.query.filter_by(user_id=user.id).order_by(Friend.created_at.desc()).all()
            
            # 格式化回應資料
            friends_list = []
            for friend in friends:
                friend_data = {
                    "id": friend.id,
                    "name": friend.name or "",
                    "relation_type": friend.relation_type
                }
                friends_list.append(friend_data)

            return {
                "status": "0",
                "message": "成功",
                "friends": friends_list
            }, 200
            
        except Exception as e:
            print(traceback.format_exc())  # 修正：移除參數 e
            return {
                "status": "1",
                "message": "取得好友列表失敗"
            }, 500
    
    @staticmethod
    def add_friend(email: str, friend_name: str, relation_type: int = 0):
        print("Adding friend...")
        try:
            # 查詢使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404
            
            # 驗證輸入
            if not friend_name or not friend_name.strip():
                return {
                    "status": "1",
                    "message": "好友名稱不能為空"
                }, 400
            
            # 驗證 relation_type
            if relation_type not in [0, 1, 2]:
                return {
                    "status": "1",
                    "message": "relation_type 參數無效"
                }, 400
            
            # 檢查是否已存在相同名稱的好友
            existing_friend = Friend.query.filter_by(
                user_id=user.id,
                name=friend_name.strip()
            ).first()
            
            if existing_friend:
                return {
                    "status": "1",
                    "message": "此好友已存在"
                }, 409
            
            # 建立新好友
            new_friend = Friend(
                user_id=user.id,
                name=friend_name.strip(),
                relation_type=relation_type,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(new_friend)
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "新增好友失敗"
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
                    "message": "使用者不存在"
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
                        "message": "日期格式錯誤，應為 YYYY-MM-DD"
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
                "message": "成功",
                "diary": diary_list
            }, 200

        except Exception as e:
            print(f"Get diary error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "取得日記失敗"
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
                    "message": "使用者不存在"
                }, 404
            
            # 驗證 badge 參數 - 允許 badge 為 0
            if badge is None:
                return {
                    "status": "1",
                    "message": "Badge 參數不能為空"
                }, 400
            
            # 驗證 badge 是否為有效整數
            try:
                badge = int(badge)
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "Badge 必須為整數"
                }, 400
            
            # 修正：允許 badge 為 0，只檢查是否小於 0
            if badge < 0:
                return {
                    "status": "1",
                    "message": "Badge 不能為負數"
                }, 400
            
            # 檢查是否有 user_default 記錄
            user_default = UserDefault.query.filter_by(user_id=user.id).first()
            
            if user_default:
                # 更新現有記錄
                user_default.badge = badge
                user_default.updated_at = datetime.now(timezone.utc)
            else:
                # 建立新記錄
                user_default = UserDefault(
                    user_id=user.id,
                    badge=badge,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.session.add(user_default)
            
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {
                "status": "1",
                "message": "更新徽章失敗"
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
                    "message": "使用者不存在"
                }, 404
            
            # 驗證 diet 參數
            if diet is not None:
                try:
                    diet = int(diet)
                except (ValueError, TypeError):
                    return {
                        "status": "1",
                        "message": "diet 參數必須為整數"
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
                "message": "成功",
                "blood_sugars": blood_sugars,
                "blood_pressures": blood_pressures,
                "weights": weights
            }, 200
            
        except Exception as e:
            print(f"Get user records error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "取得健康記錄失敗"
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
                    "message": "使用者不存在"
                }, 404
            
            # 驗證必要參數
            if sugar is None:
                return {
                    "status": "1",
                    "message": "sugar 參數不能為空"
                }, 400
            
            # 驗證血糖值
            try:
                sugar = float(sugar)
                if sugar <= 0 or sugar > 1000:
                    return {
                        "status": "1",
                        "message": "血糖值無效"
                    }, 400
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "血糖值必須為數字"
                }, 400
            
            # 處理記錄時間
            if recorded_at:
                try:
                    recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    recorded_datetime = recorded_datetime.replace(tzinfo=timezone.utc)
                except ValueError:
                    return {
                        "status": "1",
                        "message": "recorded_at 格式錯誤，應為 YYYY-MM-DD HH:MM:SS"
                    }, 400
            else:
                recorded_datetime = datetime.now(timezone.utc)
            
            # 建立血糖記錄
            new_blood_sugar = Diary(
                user_id=user.id,
                sugar=sugar,
                timeperiod=timeperiod or 0,
                drug=drug or 0,
                exercise=exercise or 0,
                type="blood_sugar",
                recorded_at=recorded_datetime,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            db.session.add(new_blood_sugar)
            db.session.commit()

            return {
                "status": "0",
                "message": "成功",
                "new_record_id": new_blood_sugar.id  # 回傳新記錄的 ID
            }, 200
        
        except Exception as e:
            db.session.rollback()
            print(f"Add blood sugar error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "新增血糖記錄失敗"
            }, 500
        


    


    @staticmethod
    def get_friend_results(email: str):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404
                
            friend_results = FriendResult.query.filter_by(user_id=user.id).order_by(FriendResult.created_at.desc()).all()
            results_list = []
            
            for result in friend_results:
                # 查詢關聯的使用者資料
                relation_user = User.query.filter_by(id=result.relation_id).first()
                
                # 確保所有欄位都不會是 None 或 null
                if relation_user:
                    relation_info = {
                        "id": result.relation_id,
                        "name": relation_user.name if relation_user.name is not None else "",
                        "account": relation_user.account if relation_user.account is not None else ""
                    }
                else:
                    # 如果找不到關聯使用者，提供預設值
                    relation_info = {
                        "id": result.relation_id,
                        "name": "",
                        "account": ""
                    }
                
                results_list.append({
                    "id": result.id,
                    "user_id": result.user_id,
                    "relation_id": result.relation_id,
                    "type": result.type if result.type is not None else "",
                    "status": result.status if result.status is not None else "",
                    "read": int(result.read) if result.read is not None else 0,
                    "created_at": result.created_at.strftime("%Y-%m-%d %H:%M:%S") if result.created_at else "",
                    "updated_at": result.updated_at.strftime("%Y-%m-%d %H:%M:%S") if result.updated_at else "",
                    "relation": relation_info
                })
                
            return {
                "status": "0",
                "message": "成功",
                "results": results_list
            }, 200
            
        except Exception as e:
            print(f"Get friend results error: {str(e)}")
            return {
                "status": "1",
                "message": "取得邀請結果失敗"
            }, 500
    

    @staticmethod
    def get_friend_requests(email: str):
        print("Getting friend requests...")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {"status": "1", "message": "使用者不存在"}, 404

            friend_requests = (
                FriendResult.query
                .filter_by(relation_id=user.id, status=0)
                .order_by(FriendResult.created_at.desc())
                .all()
            )

            try:
                from datetime import UTC as _UTC
                TZ = _UTC
            except Exception:
                from datetime import timezone
                TZ = timezone.utc

            def safe_strftime(dt, fmt="%Y-%m-%d %H:%M:%S"):
                if not isinstance(dt, datetime):
                    return ""
                if dt.tzinfo is not None:
                    return dt.astimezone(TZ).strftime(fmt)
                return dt.strftime(fmt)

            requests_list = []
            for req in friend_requests:
                from_user = User.query.filter_by(id=req.user_id).first()

                # 確保字串，不回傳 null
                user_info = {
                    "id": req.user_id,
                    "name": (getattr(from_user, "name", "") or ""),
                    "account": (getattr(from_user, "account", "") or "")
                }

                requests_list.append({
                    "id": req.id,
                    "user_id": req.user_id,
                    "relation_id": req.relation_id,
                    "type": int(getattr(req, "type", 0) or 0),
                    # 內層 status 仍保留（避免動到前端），確保是整數
                    "status": int(getattr(req, "status", 0) or 0),
                    "read": int(getattr(req, "read", 0) or 0),
                    "created_at": safe_strftime(getattr(req, "created_at", None)),
                    "updated_at": safe_strftime(getattr(req, "updated_at", None)),
                    "user": user_info
                })

            return {"status": "0", "message": "成功", "requests": requests_list}, 200

        except Exception as e:
            print(f"Get friend requests error: {str(e)}")
            return {"status": "1", "message": "取得邀請列表失敗"}, 500

        



    @staticmethod
    def add_weight(email: str, weight: float, bmi: float = None, body_fat: float = None, height: float = None):
        user = User.query.filter_by(email=email).first()
        if not user:
            return {
                "status": "1",
                "message": "使用者不存在"
            }, 404

        # 參數型態安全轉換
        try:
            if height is not None:
                height = float(height)
                if height <= 0 or height > 300:
                    return {
                        "status": "1",
                        "message": "height 參數無效"
                    }, 400
            else:
                height = 170.0  # 預設值，可依需求調整

            if weight is not None:
                weight = float(weight)
                if weight <= 0 or weight > 500:
                    return {
                        "status": "1",
                        "message": "weight 參數無效"
                    }, 400
            else:
                return {
                    "status": "1",
                    "message": "weight 參數不能為空"
                }, 400

            if bmi is not None:
                bmi = float(bmi)
                if bmi <= 0 or bmi > 100:
                    return {
                        "status": "1",
                        "message": "bmi 參數無效"
                    }, 400
            else:
                bmi = round(weight / ((height / 100) ** 2), 2)

            if body_fat is not None:
                body_fat = float(body_fat)
                if body_fat < 0 or body_fat > 100:
                    return {
                        "status": "1",
                        "message": "body_fat 參數無效"
                    }, 400
            else:
                body_fat = 0.0

        except (ValueError, TypeError):
            return {
                "status": "1",
                "message": "參數型態錯誤"
            }, 400
        

        # 新增體重記錄到 Diary
        try:
            new_diary = Diary(
                user_id=user.id,
                weight=weight,
                body_fat=body_fat,
                bmi=bmi,
                type="weight",
                recorded_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(new_diary)
            db.session.commit()
            return {
                "status": "0",
                "message": "成功",
                "new_record_id": new_diary.id
            }, 200
        except Exception as e:
            print(traceback.format_exc())
            db.session.rollback()
            return {
                "status": "1",
                "message": "新增體重失敗"
            }, 500
        




    @staticmethod
    def delete_user_records(email: str, delete_ids):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
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
                    "message": "deleteObject 必須為 ID 數字陣列"
                }, 400

            # 轉成 int
            delete_ids = [int(i) for i in delete_ids]

            Diary.query.filter(Diary.user_id == user.id, Diary.id.in_(delete_ids)).delete(synchronize_session=False)
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Delete user records error: {str(e)}")
            return {
                "status": "1",
                "message": "刪除健康記錄失敗"
            }, 500
        


    @staticmethod
    def add_diet_record(email: str, description: str, meal: int, tag: list, image: int, lat: float, lng: float, recorded_at: str):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 處理時間
            if recorded_at:
                try:
                    recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    recorded_datetime = recorded_datetime.replace(tzinfo=timezone.utc)
                except Exception:
                    recorded_datetime = datetime.now(timezone.utc)
            else:
                recorded_datetime = datetime.now(timezone.utc)

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
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(new_diary)
            db.session.commit()

            # 假設 image_url 由前端或其他服務產生，這裡先回傳空字串
            return {
                "status": "0",
                "message": "成功",
                "image_url": ""
            }, 201

        except Exception as e:
            db.session.rollback()
            print(f"Add diet record error: {str(e)}")
            return {
                "status": "1",
                "message": "新增飲食記錄失敗"
            }, 500
        


    @staticmethod
    def add_blood_pressure(email: str, systolic, diastolic, pulse, recorded_at: str = None):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 重新啟用參數驗證 - 這是關鍵修正
            if systolic is None or diastolic is None or pulse is None:
                return {
                    "status": "1",
                    "message": "血壓或心跳參數不能為空"
                }, 400

            # 安全的型態轉換，支援字串和數字
            try:
                systolic = int(float(systolic)) if systolic is not None else 0
                diastolic = int(float(diastolic)) if diastolic is not None else 0
                pulse = int(float(pulse)) if pulse is not None else 0
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "血壓或心跳必須為數字"
                }, 400

            # 現在可以安全地進行數值比較
            if systolic <= 0 or diastolic <= 0 or pulse <= 0:
                return {
                    "status": "1",
                    "message": "血壓或心跳值無效"
                }, 400

            # 處理記錄時間
            if recorded_at:
                try:
                    recorded_datetime = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    recorded_datetime = recorded_datetime.replace(tzinfo=timezone.utc)
                except Exception:
                    recorded_datetime = datetime.now(timezone.utc)
            else:
                recorded_datetime = datetime.now(timezone.utc)

            # 新增血壓記錄
            new_pressure = Diary(
                user_id=user.id,
                systolic=systolic,
                diastolic=diastolic,
                pulse=pulse,
                type="blood_pressure",
                recorded_at=recorded_datetime,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(new_pressure)
            db.session.commit()

            return {
                "status": "0",
                "message": "成功",
                "records": "成功"
            }, 201

        except Exception as e:
            db.session.rollback()
            print(f"Add blood pressure error: {str(e)}")
            print(traceback.format_exc())
            return {
                "status": "1",
                "message": "新增血壓記錄失敗",
                "records": "失敗"
            }, 500
        


    @staticmethod
    def get_friend_invite_code(email: str):
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 生成基於 user_id 的固定格式邀請碼
            # 格式：用戶ID(4位) + 隨機數(4位)
            user_id_str = f"{user.id:04d}"  # 補零到4位數
            random_suffix = f"{random.randint(1000, 9999)}"
            invite_code = user_id_str + random_suffix
            
            return {
                "status": "0",
                "message": "成功",
                "invite_code": invite_code
            }, 200

        except Exception as e:
            print(f"Get friend invite code error: {str(e)}")
            return {
                "status": "1",
                "message": "取得邀請碼失敗"
            }, 500

    @staticmethod
    def send_friend_invite(email, invite_code, relation_type):
        try:
        # 查詢發送邀請的使用者
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 驗證參數
            if not invite_code or not invite_code.strip():
                return {
                    "status": "1",
                    "message": "邀請碼不能為空"
                }, 400

            # 驗證 relation_type
            try:
                relation_type = int(relation_type)
                if relation_type not in [0, 1, 2]:
                    return {
                        "status": "1",
                        "message": "relation_type 參數無效"
                    }, 400
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "relation_type 必須為整數"
                }, 400

            # 檢查邀請碼是否有效（透過邀請碼找到目標使用者）
            target_user = AuthController.find_user_by_invite_code(invite_code)
            if not target_user:
                return {
                    "status": "1",
                    "message": "邀請碼無效"
                }, 400

            # 檢查是否是自己邀請自己
            # if target_user.id == user.id:
            #     return {
            #         "status": "1",
            #         "message": "不能邀請自己"
            #     }, 400

            # 檢查是否已經是好友
            if AuthController.is_already_friend(user.id, target_user.id, relation_type):
                return {
                    "status": "2",
                    "message": "已經成為好友"
                }, 200

            # 建立好友邀請記錄
            friend_result = FriendResult(
                user_id=user.id,
                relation_id=target_user.id,
                type=relation_type,
                status=0,  # 0: 待處理, 1: 接受, 2: 拒絕
                read=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(friend_result)
            db.session.commit()

            return {
                "status": "0",
                "message": "邀請已發送"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Send friend invite error: {str(e)}")
            return {
                "status": "1",
                "message": "發送邀請失敗"
            }, 500

    @staticmethod
    def find_user_by_invite_code(invite_code):
        """
        根據邀請碼找到對應的使用者
        邀請碼格式：前4位是 user_id，後4位是隨機數
        """
        try:
            if not invite_code or len(invite_code) != 8:
                return None
            
            # 解析邀請碼前4位作為 user_id
            try:
                user_id = int(invite_code[:4])
                return User.query.filter_by(id=user_id).first()
            except (ValueError, TypeError):
                return None
            
        except Exception as e:
            print(f"Find user by invite code error: {str(e)}")
            return None

    @staticmethod
    def is_already_friend(user_id, target_user_id, relation_type):
        """
        檢查兩個使用者是否已經是指定類型的好友
        """
        try:
            # 檢查雙向好友關係
            existing_friend = Friend.query.filter(
                db.or_(
                    db.and_(Friend.user_id == user_id, Friend.relation_type == relation_type),
                    db.and_(Friend.user_id == target_user_id, Friend.relation_type == relation_type)
                )
            ).first()
            
            return existing_friend is not None
            
        except Exception as e:
            print(f"Is already friend error: {str(e)}")
            return False

    @staticmethod
    def accept_friend_invite(email: str, invite_id: int):
        """
        接受控糖團邀請
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 查詢邀請記錄
            invite = FriendResult.query.filter_by(
                id=invite_id,
                relation_id=user.id,  # 被邀請者是當前使用者
                status=0  # 待處理狀態
            ).first()

            if not invite:
                return {
                    "status": "1",
                    "message": "邀請不存在或已處理"
                }, 404

            # 更新邀請狀態為接受
            invite.status = 1  # 1: 接受
            invite.updated_at = datetime.now(timezone.utc)

            # 建立雙向好友關係
            # 邀請者 -> 被邀請者
            friend1 = Friend(
                user_id=invite.user_id,
                name=user.name or user.account or f"使用者{user.id}",
                relation_type=invite.type,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # 被邀請者 -> 邀請者
            inviter = User.query.filter_by(id=invite.user_id).first()
            friend2 = Friend(
                user_id=user.id,
                name=inviter.name or inviter.account or f"使用者{inviter.id}",
                relation_type=invite.type,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            db.session.add(friend1)
            db.session.add(friend2)
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Accept friend invite error: {str(e)}")
            return {
                "status": "1",
                "message": "接受邀請失敗"
            }, 500

    @staticmethod
    def refuse_friend_invite(email: str, invite_id: int):
        """
        拒絕控糖團邀請
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return {
                    "status": "1",
                    "message": "使用者不存在"
                }, 404

            # 查詢邀請記錄
            invite = FriendResult.query.filter_by(
                id=invite_id,
                relation_id=user.id,  # 被邀請者是當前使用者
                status=0  # 待處理狀態
            ).first()

            if not invite:
                return {
                    "status": "1",
                    "message": "邀請不存在或已處理"
                }, 404

            # 更新邀請狀態為拒絕
            invite.status = 2  # 2: 拒絕
            invite.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Refuse friend invite error: {str(e)}")
            return {
                "status": "1",
                "message": "拒絕邀請失敗"
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
                    "message": "使用者不存在"
                }, 404

            # 驗證參數
            if not isinstance(friend_ids, list) or not friend_ids:
                return {
                    "status": "1",
                    "message": "請提供要刪除的好友 ID"
                }, 400

            # 轉換為整數
            try:
                friend_ids = [int(fid) for fid in friend_ids]
            except (ValueError, TypeError):
                return {
                    "status": "1",
                    "message": "好友 ID 格式錯誤"
                }, 400

            # 刪除好友記錄
            deleted_count = Friend.query.filter(
                Friend.user_id == user.id,
                Friend.id.in_(friend_ids)
            ).delete(synchronize_session=False)

            db.session.commit()

            return {
                "status": "0",
                "message": "成功"
            }, 200

        except Exception as e:
            db.session.rollback()
            print(f"Remove friends error: {str(e)}")
            return {
                "status": "1",
                "message": "刪除好友失敗"
            }, 500