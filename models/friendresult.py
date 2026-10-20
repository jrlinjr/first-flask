from utils.extensions import db
from utils.time_utils import now_taiwan
from sqlalchemy.orm import relationship

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
        default=now_taiwan
    )
    updated_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=now_taiwan,
        onupdate=now_taiwan
    )
    
    # 邀請發送者關聯
    user = relationship(
        "User", 
        foreign_keys=[user_id], 
        backref=db.backref("sent_invites", lazy='dynamic'),
        lazy='select'
    )
    # 被邀請者關聯
    relation_user = relationship(
        "User", 
        foreign_keys=[relation_id], 
        backref=db.backref("received_invites", lazy='dynamic'),
        lazy='select'
    )

    # 性能優化的復合索引
    __table_args__ = (
        db.Index('idx_user_relation_type_status', 'user_id', 'relation_id', 'type', 'status'),
        db.Index('idx_relation_status', 'relation_id', 'status'),
        db.Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<FriendResult {self.id}: {self.user_id} -> {self.relation_id}, status: {self.status}>"

    def to_dict(self):
        """轉換為字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "relation_id": self.relation_id,
            "type": self.type,
            "status": self.status,
            "read": self.read,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
            "user_name": self.user.name if self.user else "",
            "relation_user_name": self.relation_user.name if self.relation_user else ""
        }

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