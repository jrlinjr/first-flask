from app.extensions import db
from datetime import datetime, timezone,timedelta

TZ_TAIWAN = timezone(timedelta(hours=8))
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), unique=True, nullable=True)  
    name = db.Column(db.String(100), nullable=True)  
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    birthday = db.Column(db.String(20), nullable=True)  
    height = db.Column(db.Float, nullable=True) 
    weight = db.Column(db.Float, nullable=True)  # 體重改為 Float
    phone = db.Column(db.String(20), nullable=True)  
    gender = db.Column(db.Boolean, nullable=True)  
    fcm_id = db.Column(db.String(255), nullable=True)  
    group = db.Column(db.String(50), nullable=True)
    fb_id = db.Column(db.String(255), nullable=True) 
    address = db.Column(db.String(255), nullable=True)
    # 修正：只保留一個 invite_code 欄位定義，使用更適合的配置
    invite_code = db.Column(db.String(20), unique=True, nullable=True, index=True)
    must_change_password = db.Column(db.Integer, default=0, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(10), nullable=True)
    verification_code_expires = db.Column(db.DateTime(timezone=True), nullable=True)
    # 移除 login_times 和 updated_at，因為資料庫中可能沒有這些欄位
    created_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(TZ_TAIWAN),
        server_default=db.text('CURRENT_TIMESTAMP')
    )

    def __repr__(self):
        return f"<User {self.email}>"
