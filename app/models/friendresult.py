from app.extensions import db
from datetime import datetime, timezone, timedelta

TZ_TAIWAN = timezone(timedelta(hours=8))

class FriendResult(db.Model):
    __tablename__ = "FriendResult"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    relation_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 修正：應該指向 users.id
    type = db.Column(db.Integer, nullable=False)  # 關係類型
    invite_code = db.Column(db.String(64), nullable=True)  # 邀請碼
    status = db.Column(db.Integer, nullable=False, default=0)  # 狀態
    read = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(TZ_TAIWAN),
        server_default=db.text('CURRENT_TIMESTAMP')
    )
    updated_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(TZ_TAIWAN),
        onupdate=datetime.now(TZ_TAIWAN),
        server_default=db.text('CURRENT_TIMESTAMP')
    )
    
    # 修正關聯設定
    user = db.relationship("User", foreign_keys=[user_id], backref="sent_invites")
    relation_user = db.relationship("User", foreign_keys=[relation_id], backref="received_invites")

    def __repr__(self):
        return f"<FriendResult {self.id}: {self.user_id} -> {self.relation_id}>"