from utils.extensions import db
from utils.time_utils import now_taiwan


class CareRecord(db.Model):
    """照護記錄（原本誤寫在 a1c_records，改成獨立一張表）"""
    __tablename__ = "care_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    care_data = db.Column(db.Text, nullable=False)  # 照護內容
    created_at = db.Column(db.DateTime, nullable=False, default=now_taiwan)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_taiwan, onupdate=now_taiwan)

    def __repr__(self):
        return f"<CareRecord {self.user_id}: {self.care_data}>"
