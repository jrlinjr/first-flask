from app.extensions import db
from datetime import datetime, timezone, timedelta
import json

# 定義台灣時區 UTC+8
TZ_TAIWAN = timezone(timedelta(hours=8))

class Diary(db.Model):
    __tablename__ = "diary"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 血壓相關
    systolic = db.Column(db.Integer, nullable=True)      # 收縮壓
    diastolic = db.Column(db.Integer, nullable=True)     # 舒張壓
    pulse = db.Column(db.Integer, nullable=True)         # 脈搏
    
    # 體重相關
    weight = db.Column(db.Float, nullable=True, default=0.0)     # 體重
    body_fat = db.Column(db.Float, nullable=True, default=0.0)   # 體脂
    bmi = db.Column(db.Float, nullable=True, default=0.0)        # BMI
    
    # 血糖
    sugar = db.Column(db.Float, nullable=True, default=0.0)      # 血糖
    
    # 其他記錄
    exercise = db.Column(db.Integer, nullable=True, default=0)   # 運動
    drug = db.Column(db.Integer, nullable=True, default=0)       # 用藥
    timeperiod = db.Column(db.Integer, nullable=True, default=0) # 時間段
    description = db.Column(db.Text, nullable=True, default="") # 描述
    meal = db.Column(db.Integer, nullable=True, default=0)       # 餐次
    
    # JSON 格式欄位
    tag = db.Column(db.JSON, nullable=True)          # 標籤 {"name": ["abc"], "message": ""}
    image = db.Column(db.JSON, nullable=True)        # 圖片 ["url1", "url2"]
    location = db.Column(db.JSON, nullable=True)     # 位置 {"lat": "", "lng": ""}
    
    reply = db.Column(db.Text, nullable=True, default="")       # 回覆
    type = db.Column(db.String(50), nullable=True, default="") # 記錄類型
    
    recorded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(TZ_TAIWAN))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(TZ_TAIWAN))
    updated_at = db.Column(
        db.DateTime, 
        nullable=False, 
        default=lambda: datetime.now(TZ_TAIWAN),
        onupdate=lambda: datetime.now(TZ_TAIWAN)
    )

    def __repr__(self):
        return f"<Diary {self.user_id}: {self.type}>"
