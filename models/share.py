from utils.extensions import db
from utils.time_utils import now_taiwan

class ShareRecord(db.Model):
    __tablename__ = "share_records"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    record_type = db.Column(db.Integer, nullable=False)  # 0:血壓 1:體重 2:血糖 3:飲食
    record_id = db.Column(db.Integer, nullable=False)    # 對應記錄的ID
    
    # 🔧 添加分享者(user)的 relationship
    user = db.relationship("User",
                          foreign_keys=[user_id],
                          backref=db.backref("shared_records", lazy='dynamic'),
                          lazy="select")
    
    # Diary 記錄的 relationship
    diary = db.relationship("Diary",
                            primaryjoin="foreign(ShareRecord.record_id)==Diary.id",
                            lazy="joined",
                            viewonly=True)
    
    relation_type = db.Column(db.Integer, nullable=False)  # 0:醫師團 1:親友團 2:控糖團
    relation_id = db.Column(db.Integer, nullable=True, default=0)  # 加上預設值 0
    shared_at = db.Column(
        db.DateTime, 
        nullable=False,
        default=now_taiwan
    )
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
        return f"<ShareRecord {self.user_id}: type={self.record_type}, relation={self.relation_type}>"