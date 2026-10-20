from utils.extensions import db
from utils.time_utils import now_taiwan

class A1cRecord(db.Model):
    __tablename__ = "a1c_records"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    a1cs = db.Column(db.Float, nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    Message = db.Column(db.String(255), nullable=True)
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
        return f"<A1cRecord {self.user_id}: {self.a1cs}>"