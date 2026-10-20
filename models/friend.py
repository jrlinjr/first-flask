from utils.extensions import db
from utils.time_utils import now_taiwan


class Friend(db.Model):
    __tablename__ = "friends"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 好友名稱
    relation_type = db.Column(db.Integer, nullable=False, default=0)  # 關係類型
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

    def __repr__(self):
        return f"<Friend {self.user_id}: {self.name}>"