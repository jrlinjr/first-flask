from app.extensions import db
from datetime import datetime, UTC

class UserVip(db.Model):
    __tablename__ = "user_vips"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # VIP 相關資訊
    level = db.Column(db.Integer, default=0)  # VIP 等級
    remark = db.Column(db.Float, default=0.0)  # 備註/評分
    started_at = db.Column(db.String(20), nullable=True)  # VIP 開始時間
    ended_at = db.Column(db.String(20), nullable=True)  # VIP 結束時間
    
    # 時間戳
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))

    # 關聯
    user = db.relationship('User', backref=db.backref('vip_info', lazy=True))

    def __repr__(self):
        return f"<UserVip {self.user_id}>"