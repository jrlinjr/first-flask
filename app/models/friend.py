from app.extensions import db
from datetime import datetime, timezone



class Friend(db.Model):
    __tablename__ = "friends"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 好友名稱
    relation_type = db.Column(db.Integer, nullable=False, default=0)  # 關係類型
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

    def __repr__(self):
        return f"<Friend {self.user_id}: {self.name}>"