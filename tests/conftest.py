"""
pytest 共用設定

- 測試一律連 `first_test` 資料庫，不會動到正式的 `first`
- 信件一律攔截（不會真的寄出），測試可以從 outbox 讀驗證碼
- 每個測試開始前清空所有資料表，id 從 1 開始，結果可重現
"""
import os
import sys
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values
from flask.testing import FlaskClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------
# 1. 在 import 專案之前先把環境變數換成測試用的
#    （load_dotenv 預設不覆蓋已存在的環境變數，所以這裡設定的會優先）
# ---------------------------------------------------------------
_dotenv = dotenv_values(ROOT / ".env")
_base_uri = os.getenv("TEST_DATABASE_URI") or _dotenv["SQLALCHEMY_DATABASE_URI"]
TEST_DB_URL = make_url(_base_uri.strip()).set(database="first_test")

os.environ["SQLALCHEMY_DATABASE_URI"] = TEST_DB_URL.render_as_string(hide_password=False)
os.environ["JWT_SECRET_KEY"] = "test-secret-key-at-least-32-bytes-long!!"
# 雙重保險：就算攔截失效，也只會連到本機一個不存在的埠，不會用真的 Gmail 寄信
os.environ["MAIL_SERVER"] = "127.0.0.1"
os.environ["MAIL_PORT"] = "1"
os.environ["MAIL_USE_TLS"] = "False"
os.environ["MAIL_USERNAME"] = "test@example.com"
os.environ["MAIL_PASSWORD"] = "not-a-real-password"
# 測試故意觸發的錯誤不要寫進 log/error.log
os.environ["LOG_TO_FILE"] = "0"

from main import create_app  # noqa: E402
from utils.extensions import db, mail, bcrypt  # noqa: E402
from models import (  # noqa: E402
    User, Diary, A1cRecord, CareRecord, News, Friend, FriendResult,
    ShareRecord, UserDefault, UserSetting, medical_records,
)

MODELS = SimpleNamespace(
    User=User, Diary=Diary, A1cRecord=A1cRecord, CareRecord=CareRecord, News=News, Friend=Friend,
    FriendResult=FriendResult, ShareRecord=ShareRecord, UserDefault=UserDefault,
    UserSetting=UserSetting, medical_records=medical_records,
)

DEFAULT_PASSWORD = "password123"


# ---------------------------------------------------------------
# 2. 會把每個請求記下來的 test client（給「重構前後回應比對」用）
#    設定環境變數 RECORD_RESPONSES=<檔案路徑> 才會記錄
# ---------------------------------------------------------------
_RECORDS: list[dict] = []
_CURRENT_TEST = {"id": ""}


class RecordingClient(FlaskClient):
    def open(self, *args, **kwargs):
        response = super().open(*args, **kwargs)
        if os.getenv("RECORD_RESPONSES"):
            request = response.request
            _RECORDS.append({
                "test": _CURRENT_TEST["id"],
                "method": request.method,
                "path": request.path,
                "query": request.query_string.decode(),
                "status": response.status_code,
                "body": response.get_json(silent=True) if response.is_json else response.get_data(as_text=True),
            })
        return response


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    _CURRENT_TEST["id"] = item.nodeid


def pytest_sessionfinish(session, exitstatus):
    path = os.getenv("RECORD_RESPONSES")
    if path:
        Path(path).write_text(json.dumps(_RECORDS, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ---------------------------------------------------------------
# 3. fixtures
# ---------------------------------------------------------------
def _ensure_test_database():
    """first_test 不存在就建立"""
    # 先不指定資料庫連上 MySQL（URL.set(database=None) 會被當成「不修改」，所以用 _replace）
    server_engine = create_engine(TEST_DB_URL._replace(database=None))
    with server_engine.connect() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS `first_test` CHARACTER SET utf8mb4"))
    server_engine.dispose()


@pytest.fixture(scope="session")
def app():
    _ensure_test_database()
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.test_client_class = RecordingClient

    # 信件只記錄、不寄出
    flask_app.extensions["mail"].suppress = True
    # 測試時把 bcrypt 調快（正式環境仍是預設 12）
    bcrypt._log_rounds = 4

    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    yield flask_app


@pytest.fixture(autouse=True)
def clean_db(app):
    """每個測試前清空資料表（TRUNCATE 也會把自動編號歸零）"""
    with app.app_context():
        db.session.remove()
        with db.engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table in db.metadata.sorted_tables:
                conn.execute(text(f"TRUNCATE TABLE `{table.name}`"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def outbox(app):
    """攔截到的信件清單"""
    with mail.record_messages() as messages:
        yield messages


@pytest.fixture
def M():
    """所有 model 類別，測試裡直接查資料庫用"""
    return MODELS


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.remove()


@pytest.fixture
def make_user(client, app):
    """走完整流程建立一個已驗證的使用者：註冊 → 從信件拿驗證碼 → 驗證 → 登入"""

    def _make_user(email: str, password: str = DEFAULT_PASSWORD, account: str | None = None):
        with mail.record_messages() as messages:
            response = client.post("/api/register", json={"email": email, "password": password, "account": account})
        assert response.status_code == 201, response.get_json()
        code = extract_code(messages[-1].body)

        response = client.post("/api/verification/check", json={"email": email, "code": code})
        assert response.status_code == 200, response.get_json()

        response = client.post("/api/auth", json={"email": email, "password": password})
        assert response.status_code == 200, response.get_json()
        token = response.get_json()["token"]

        with app.app_context():
            user_id = User.query.filter_by(email=email).first().id
        return SimpleNamespace(
            id=user_id,
            email=email,
            password=password,
            token=token,
            headers={"Authorization": f"Bearer {token}"},
        )

    return _make_user


@pytest.fixture
def alice(make_user):
    return make_user("alice@example.com", account="alice")


@pytest.fixture
def bob(make_user):
    return make_user("bob@example.com", account="bob")


def extract_code(mail_body: str) -> str:
    """從「您的驗證碼是: 123456，15分鐘內有效。」取出 6 位數驗證碼"""
    digits = ""
    for char in mail_body.split(":", 1)[1]:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return digits
