from app.extensions import db
from datetime import datetime, timezone

class medical_records(db.Model):
    __tablename__ = "medical_records"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    diabetes_type = db.Column(db.String(20), default="無", nullable=True)  # 糖尿病類型
    oad = db.Column(db.Float, default=0.0, nullable=True)  # 口服降糖藥物劑量
    insulin = db.Column(db.Float, default=0.0, nullable=True)  # 胰島素劑量
    anti_hypertensives = db.Column(db.Float, default=0.0, nullable=True)  # 抗高血壓藥物劑量

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

    # 關聯
    user = db.relationship('User', backref=db.backref('medical_records', lazy=True))

    def __repr__(self):
        return f"<MedicalRecord {self.user_id}>"