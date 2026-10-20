"""
Flask 擴充套件的實例

先在這裡建好「空的」物件，等 main.create_app() 再用 init_app(app) 綁到 app 上，
這樣 models / services 可以直接 import 使用，不會有循環 import。
"""
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_mail import Mail

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
migrate = Migrate()
mail = Mail()
