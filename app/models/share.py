from app.extensions import db
from datetime import datetime, timezone

class ShareRecord(db.Model):
    __tablename__ = "share_records"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    record_type = db.Column(db.Integer, nullable=False)  # 0:血壓 1:體重 2:血糖 3:飲食
    record_id = db.Column(db.Integer, nullable=False)    # 對應記錄的ID
    relation_type = db.Column(db.Integer, nullable=False)  # 1:親友 2:糖友
    relation_id = db.Column(db.Integer, nullable=True, default=0)  # 加上預設值 0
    shared_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(timezone.utc)
    )
    created_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<ShareRecord {self.user_id}: type={self.record_type}, relation={self.relation_type}>"