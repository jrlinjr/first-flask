from app.extensions import db
from datetime import datetime, timezone

class News(db.Model):
    __tablename__ = "news"
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group = db.Column(db.Integer, nullable=False, default=1)  # 群組分類
    title = db.Column(db.String(255), nullable=False)        # 標題
    message = db.Column(db.Text, nullable=False)             # 內容
    pushed_at = db.Column(db.DateTime, nullable=True)        # 推送時間
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
        return f"<News {self.id}: {self.title}>"