from app.extensions import db
from datetime import datetime, UTC

class FriendResult(db.Model):
    __tablename__ = "FriendResult"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    relation_id = db.Column(db.Integer, db.ForeignKey('friends.id'), nullable=False)
    type = db.Column(db.Integer, nullable=False)  # 關係類型
    status = db.Column(db.Integer, nullable=False, default=0)  # 狀態
    read = db.Column(db.Boolean, default=False)  # 是否已讀
    created_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(UTC),
        server_default=db.text('CURRENT_TIMESTAMP')
    )
    updated_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(UTC),
        onupdate=datetime.now(UTC),
        server_default=db.text('CURRENT_TIMESTAMP')
    )
    relation = db.relationship('Friend', backref=db.backref('friend_results', lazy=True))

    def __repr__(self):
        return f"<FriendResult {self.id}>"
