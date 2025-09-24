from app.extensions import db
from datetime import datetime, UTC

class UserSetting(db.Model):
    __tablename__ = "user_settings"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 通知設定
    after_recording = db.Column(db.Integer, default=0)  # 記錄後通知
    no_recording_for_a_day = db.Column(db.Integer, default=0)  # 一天未記錄通知
    over_max_or_under_min = db.Column(db.Integer, default=0)  # 超過最大值或低於最小值通知
    after_meal = db.Column(db.Integer, default=0)  # 餐後通知
    
    # 單位設定
    unit_of_sugar = db.Column(db.Integer, default=0)  # 血糖單位
    unit_of_weight = db.Column(db.Integer, default=0)  # 體重單位
    unit_of_height = db.Column(db.Integer, default=0)  # 身高單位
    
    # 時間戳
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))

    # 關聯
    user = db.relationship('User', backref=db.backref('settings', lazy=True))

    def __repr__(self):
        return f"<UserSetting {self.user_id}>"