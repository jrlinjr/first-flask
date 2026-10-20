"""
程式進入點

啟動（開發用）：
    .venv/bin/python main.py
    PORT=5001 .venv/bin/python main.py    # 5000 被 macOS AirPlay 佔用時

分層：controllers（接 request）→ services（商業邏輯 + DB）→ utils / models
"""
import json
import traceback

from flask import Flask, request
from flask_migrate import upgrade
from werkzeug.exceptions import HTTPException

from shared import env
from controllers import auth_bp, user_bp, record_bp, friend_bp, share_bp, news_bp
from utils.api_response import error_body
from utils.extensions import db, bcrypt, jwt, migrate, mail
from utils.logger import logger


def create_app() -> Flask:
    app = Flask(__name__)

    # 資料庫連線池
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 5,
        "pool_recycle": 300,      # 5 分鐘回收連線，避免 MySQL 斷線
        "pool_pre_ping": True,    # 用之前先確認連線還活著
        "max_overflow": 0,
        "pool_timeout": 30,
    }

    # JWT：從 Authorization: Bearer <token> 取
    app.config["JWT_SECRET_KEY"] = env.jwt_secret_key
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    app.config["JWT_ERROR_MESSAGE_KEY"] = "message"

    # 資料庫
    app.config["SQLALCHEMY_DATABASE_URI"] = env.database_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # 郵件
    app.config.update(
        MAIL_SERVER=env.mail_server,
        MAIL_PORT=env.mail_port,
        MAIL_USE_TLS=env.mail_use_tls,
        MAIL_USERNAME=env.mail_username,
        MAIL_PASSWORD=env.mail_password,
        MAIL_DEFAULT_SENDER=env.mail_username,
    )

    # 初始化所有擴充套件
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # 註冊路由，全部掛在 /api 底下
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(user_bp, url_prefix="/api")
    app.register_blueprint(record_bp, url_prefix="/api")
    app.register_blueprint(friend_bp, url_prefix="/api")
    app.register_blueprint(share_bp, url_prefix="/api")
    app.register_blueprint(news_bp, url_prefix="/api")

    # 全域錯誤處理：沒被接住的例外一律回 500
    # 404 / 405 這類 HTTP 錯誤保留原本的狀態碼和 header（例如 405 的 Allow），只把內容換成 JSON
    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            logger.warning(f"{request.method} {request.path} → {e.code} {e.name}")
            response = e.get_response()
            response.set_data(json.dumps(error_body(e.name, e.name.upper().replace(" ", "_"))))
            response.content_type = "application/json"
            return response

        logger.error(f"未處理的例外：{e}")
        logger.error(traceback.format_exc())
        return {"status": "1", "message": "系統錯誤"}, 500

    return app


# 給 flask 指令（flask --app main db upgrade）或 gunicorn（gunicorn main:app）用
app = create_app()


if __name__ == "__main__":
    # 啟動前先把資料庫升到最新版本（套用 migrations/versions 裡還沒跑過的 migration）
    # 不要再用 db.create_all()：它建的表不會記在 migration 裡，換一台資料庫就會少表
    with app.app_context():
        upgrade()
        logger.info("資料庫已是最新版本")
    app.run(debug=True, port=env.port)
