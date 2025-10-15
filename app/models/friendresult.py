from app.extensions import db
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import relationship

TZ_TAIWAN = timezone(timedelta(hours=8))

class FriendResult(db.Model):
    __tablename__ = "FriendResult"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True) # 邀請發送者
    relation_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True) # 邀請接收者
    
    type = db.Column(db.Integer, nullable=False)  # 關係類型 (0:醫師團, 1:親友團, 2:控糖團)
    status = db.Column(db.Integer, nullable=False, default=0)  # 狀態 (0:待處理, 1:接受, 2:拒絕)
    read = db.Column(db.Integer, default=0, nullable=False) # 是否已讀 (0:未讀, 1:已讀)
    
    created_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=lambda: datetime.now(TZ_TAIWAN)
    )
    updated_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=lambda: datetime.now(TZ_TAIWAN),
        onupdate=lambda: datetime.now(TZ_TAIWAN)
    )
    
    # 🔧 修復關聯定義 - 保持前端兼容性
    # 邀請發送者 - 保持 'user' 名稱給前端使用
    user = relationship(
        "User", 
        foreign_keys=[user_id], 
        backref=db.backref("sent_invites", lazy='dynamic'),  # 使用 db.backref 避免衝突
        lazy='select'
    )
    
    # 邀請接收者 - 保持 'relation_user' 名稱給前端使用  
    relation_user = relationship(
        "User", 
        foreign_keys=[relation_id], 
        backref=db.backref("received_invites", lazy='dynamic'),  # 使用 db.backref 避免衝突
        lazy='select'
    )

    # 🚀 添加性能優化的復合索引
    __table_args__ = (
        db.Index('idx_user_relation_type_status', 'user_id', 'relation_id', 'type', 'status'),
        db.Index('idx_relation_status', 'relation_id', 'status'),
        db.Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<FriendResult {self.id}: {self.user_id} -> {self.relation_id}, status: {self.status}>"

    # 🎯 添加安全的輔助方法 - 不影響前端現有邏輯
    def to_dict(self):
        """轉換為前端安全的字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "relation_id": self.relation_id,
            "type": self.type,
            "status": self.status,
            "read": self.read,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
            # 安全地包含用戶信息
            "user_name": self.user.name if self.user else "",
            "relation_user_name": self.relation_user.name if self.relation_user else ""
        }

    def safe_user_name(self):
        """安全獲取發送者名稱 - 處理中文字符"""
        if not self.user or not self.user.name:
            return f"User{self.user_id}"
        try:
            self.user.name.encode('ascii')
            return self.user.name
        except UnicodeEncodeError:
            return f"User{self.user_id}"

    def safe_relation_user_name(self):
        """安全獲取接收者名稱 - 處理中文字符"""
        if not self.relation_user or not self.relation_user.name:
            return f"User{self.relation_id}"
        try:
            self.relation_user.name.encode('ascii')
            return self.relation_user.name
        except UnicodeEncodeError:
            return f"User{self.relation_id}"

    @property
    def relation_type_name(self):
        """關係類型的可讀名稱"""
        type_names = {
            0: "doctor_group",
            1: "family_group", 
            2: "diabetes_group"
        }
        return type_names.get(self.type, "unknown")

    @property
    def status_name(self):
        """狀態的可讀名稱"""
        status_names = {
            0: "pending",
            1: "accepted",
            2: "rejected"
        }
        return status_names.get(self.status, "unknown")