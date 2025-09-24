from app import create_app
from app.extensions import db

app = create_app()

# 建立所有表
with app.app_context():
    db.create_all()
    print("All tables created successfully!")

if __name__ == "__main__":
    app.run(debug=True)
