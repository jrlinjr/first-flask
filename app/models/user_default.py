from app.extensions import db
from datetime import datetime, timezone

class UserDefault(db.Model):
    __tablename__ = "user_defaults"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 確保有 badge 欄位
    badge = db.Column(db.Integer, nullable=True, default=0)
    
    # 血糖相關設定
    sugar_delta_max = db.Column(db.Float, nullable=True)
    sugar_delta_min = db.Column(db.Float, nullable=True)
    sugar_morning_max = db.Column(db.Float, nullable=True)
    sugar_morning_min = db.Column(db.Float, nullable=True)
    sugar_evening_max = db.Column(db.Float, nullable=True)
    sugar_evening_min = db.Column(db.Float, nullable=True)
    sugar_before_max = db.Column(db.Float, nullable=True)
    sugar_before_min = db.Column(db.Float, nullable=True)
    sugar_after_max = db.Column(db.Float, nullable=True)
    sugar_after_min = db.Column(db.Float, nullable=True)
    
    # 血壓相關設定
    systolic_max = db.Column(db.Integer, nullable=True)
    systolic_min = db.Column(db.Integer, nullable=True)
    diastolic_max = db.Column(db.Integer, nullable=True)
    diastolic_min = db.Column(db.Integer, nullable=True)
    pulse_max = db.Column(db.Integer, nullable=True)
    pulse_min = db.Column(db.Integer, nullable=True)
    
    # 體重和身體組成相關設定
    weight_max = db.Column(db.Float, nullable=True)
    weight_min = db.Column(db.Float, nullable=True)
    bmi_max = db.Column(db.Float, nullable=True)
    bmi_min = db.Column(db.Float, nullable=True)
    body_fat_max = db.Column(db.Float, nullable=True)
    body_fat_min = db.Column(db.Float, nullable=True)


    #身高體重設定
    height = db.Column(db.Float, nullable=True) 
    weight = db.Column(db.Float, nullable=True)
    birthday = db.Column(db.String(20), nullable=True) 
    # 時間戳
    created_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )

    # 關聯
    user = db.relationship('User', backref=db.backref('default_settings', lazy=True))

    def __repr__(self):
        return f"<UserDefault {self.user_id}: badge={self.badge}>"