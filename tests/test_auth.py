"""註冊、驗證碼、登入、忘記密碼、重設密碼"""
from datetime import datetime

import pytest

from conftest import DEFAULT_PASSWORD, extract_code


# ---------------- 註冊 POST /api/register ----------------

def test_register_success_sends_code_and_creates_default_groups(client, outbox, M, db_session):
    response = client.post("/api/register", json={"email": "new@example.com", "password": DEFAULT_PASSWORD, "account": "newbie"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "0"
    assert body["message_code"] == "REGISTRATION_SUCCESS"
    assert body["needs_verification"] is True

    # 寄出一封含 6 位數驗證碼的信
    assert len(outbox) == 1
    assert outbox[0].recipients == ["new@example.com"]
    assert len(extract_code(outbox[0].body)) == 6

    # 新使用者自動有三個預設好友分組
    user = M.User.query.filter_by(email="new@example.com").first()
    assert user.is_verified is False
    assert user.account == "newbie"
    groups = sorted((f.relation_type, f.name) for f in M.Friend.query.filter_by(user_id=user.id))
    assert groups == [(0, "醫師團"), (1, "親友團"), (2, "控糖團")]


@pytest.mark.parametrize("payload, status, code", [
    ({"email": "not-an-email", "password": DEFAULT_PASSWORD}, 400, "INVALID_EMAIL_FORMAT"),
    ({"email": "", "password": DEFAULT_PASSWORD}, 400, "INVALID_EMAIL_FORMAT"),
    ({"email": "a@b.com", "password": "short"}, 400, "PASSWORD_TOO_SHORT"),
    ({}, 400, "INVALID_EMAIL_FORMAT"),
])
def test_register_validation(client, payload, status, code):
    response = client.post("/api/register", json=payload)
    assert response.status_code == status
    assert response.get_json()["message_code"] == code


def test_register_again_while_unverified_updates_user(client, outbox):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    response = client.post("/api/register", json={"email": "u@example.com", "password": "another-password"})

    assert response.status_code == 200
    assert response.get_json()["message_code"] == "REGISTRATION_SUCCESS"
    assert len(outbox) == 2


def test_register_verified_email_is_rejected(client, alice):
    response = client.post("/api/register", json={"email": alice.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 409
    assert response.get_json()["message_code"] == "EMAIL_REGISTERED_VERIFIED"


def test_register_duplicate_account_is_rejected(client, alice):
    response = client.post("/api/register", json={"email": "other@example.com", "password": DEFAULT_PASSWORD, "account": "alice"})
    assert response.status_code == 409
    assert response.get_json()["message_code"] == "ACCOUNT_ALREADY_USED"


# ---------------- 檢查 email GET /api/register/check ----------------

def test_check_email_available(client):
    response = client.get("/api/register/check?email=free@example.com")
    assert response.status_code == 200
    body = response.get_json()
    assert body["message_code"] == "EMAIL_AVAILABLE"
    assert body["user_exists"] is False


def test_check_email_empty(client):
    response = client.get("/api/register/check?email=")
    # 原本的寫法：status "1" 但 HTTP 是 200
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "EMAIL_REQUIRED"


def test_check_email_invalid_format(client):
    response = client.get("/api/register/check?email=bad")
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "INVALID_EMAIL_FORMAT"


def test_check_email_unverified_resends_code(client, outbox):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    response = client.get("/api/register/check?email=u@example.com")

    assert response.status_code == 200
    body = response.get_json()
    assert body["message_code"] == "EMAIL_REGISTERED_UNVERIFIED"
    assert body["needs_verification"] is True
    assert len(outbox) == 2


def test_check_email_verified(client, alice):
    response = client.get(f"/api/register/check?email={alice.email}")
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "EMAIL_REGISTERED_VERIFIED"


# ---------------- 登入 POST /api/auth ----------------

def test_login_success_returns_token(client, alice):
    response = client.post("/api/auth", json={"email": alice.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 200
    body = response.get_json()
    assert body["message_code"] == "LOGIN_SUCCESS"
    assert body["token"]


@pytest.mark.parametrize("payload, status, code", [
    ({"email": "alice@example.com", "password": "wrong-password"}, 401, "INVALID_CREDENTIALS"),
    ({"email": "nobody@example.com", "password": DEFAULT_PASSWORD}, 401, "INVALID_CREDENTIALS"),
    ({"email": "bad", "password": DEFAULT_PASSWORD}, 400, "INVALID_EMAIL_FORMAT"),
    ({"email": "alice@example.com", "password": ""}, 400, "PASSWORD_REQUIRED"),
])
def test_login_failures(client, alice, payload, status, code):
    response = client.post("/api/auth", json=payload)
    assert response.status_code == status
    assert response.get_json()["message_code"] == code


# ---------------- Email 驗證不能被繞過 ----------------

def test_login_unverified_is_rejected(client, outbox):
    """攻擊流程：用別人的 email 註冊（收不到驗證信）→ 直接登入，不能拿到 token"""
    client.post("/api/register", json={"email": "victim@example.com", "password": DEFAULT_PASSWORD})

    response = client.post("/api/auth", json={"email": "victim@example.com", "password": DEFAULT_PASSWORD})
    assert response.status_code == 403
    body = response.get_json()
    assert body["status"] == "1"
    assert body["message_code"] == "EMAIL_NOT_VERIFIED"
    assert body["needs_verification"] is True
    assert "token" not in body


def test_login_unverified_wrong_password_is_invalid_credentials(client, outbox):
    """未驗證 + 密碼錯：跟帳號不存在一樣回 401，不透露這個 email 有註冊過"""
    client.post("/api/register", json={"email": "victim@example.com", "password": DEFAULT_PASSWORD})

    response = client.post("/api/auth", json={"email": "victim@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.get_json()["message_code"] == "INVALID_CREDENTIALS"


def test_login_after_verification_succeeds(client, outbox):
    """真正的 email 主人從信裡拿到驗證碼、驗證完，就可以登入"""
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    code = extract_code(outbox[0].body)
    client.post("/api/verification/check", json={"email": "u@example.com", "code": code, "password": DEFAULT_PASSWORD})

    response = client.post("/api/auth", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_verify_requires_password(client, outbox, M, db_session):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    code = extract_code(outbox[0].body)

    response = client.post("/api/verification/check", json={"email": "u@example.com", "code": code})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "PASSWORD_REQUIRED"
    assert M.User.query.filter_by(email="u@example.com").first().is_verified is False


def test_verify_wrong_password(client, outbox, M, db_session):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    code = extract_code(outbox[0].body)

    response = client.post("/api/verification/check", json={"email": "u@example.com", "code": code, "password": "wrong-password"})
    assert response.status_code == 401
    assert response.get_json()["message_code"] == "INVALID_CREDENTIALS"
    assert M.User.query.filter_by(email="u@example.com").first().is_verified is False


def test_reregister_cannot_take_over_unverified_account(client, outbox):
    """攻擊流程：本人先註冊、還沒驗證 → 別人用同一個 email 重新註冊、換掉密碼
    → 本人拿最新的驗證碼驗證，不能讓帳號帶著別人設的密碼被啟用"""
    client.post("/api/register", json={"email": "victim@example.com", "password": "victim-password"})
    client.post("/api/register", json={"email": "victim@example.com", "password": "attacker-password"})
    latest_code = extract_code(outbox[-1].body)

    response = client.post("/api/verification/check", json={"email": "victim@example.com", "code": latest_code, "password": "victim-password"})
    assert response.status_code == 401
    assert response.get_json()["message_code"] == "INVALID_CREDENTIALS"

    # 帳號還沒啟用，別人的密碼拿不到 token
    response = client.post("/api/auth", json={"email": "victim@example.com", "password": "attacker-password"})
    assert response.status_code == 403

    # 本人重新註冊把密碼換回來，再驗證就成功；別人的密碼從此登不進去
    client.post("/api/register", json={"email": "victim@example.com", "password": "victim-password"})
    code = extract_code(outbox[-1].body)
    response = client.post("/api/verification/check", json={"email": "victim@example.com", "code": code, "password": "victim-password"})
    assert response.status_code == 200
    assert client.post("/api/auth", json={"email": "victim@example.com", "password": "victim-password"}).status_code == 200
    assert client.post("/api/auth", json={"email": "victim@example.com", "password": "attacker-password"}).status_code == 401


def test_squatted_email_owner_can_still_verify(client, outbox):
    """攻擊流程：別人先用本人的 email 搶先註冊 → 本人之後註冊（密碼蓋掉別人的）
    → 本人用自己的密碼驗證成功，別人的密碼登不進去"""
    client.post("/api/register", json={"email": "victim@example.com", "password": "attacker-password"})
    client.post("/api/register", json={"email": "victim@example.com", "password": "victim-password"})
    code = extract_code(outbox[-1].body)

    response = client.post("/api/verification/check", json={"email": "victim@example.com", "code": code, "password": "victim-password"})
    assert response.status_code == 200
    assert client.post("/api/auth", json={"email": "victim@example.com", "password": "victim-password"}).status_code == 200
    assert client.post("/api/auth", json={"email": "victim@example.com", "password": "attacker-password"}).status_code == 401


def test_get_user_does_not_expose_verification_code(client, alice, M, db_session):
    """GET /api/user 不回傳驗證碼（就算資料庫裡有一組還沒用掉的驗證碼）"""
    client.post("/api/verification/send", json={"email": alice.email})
    assert M.User.query.filter_by(email=alice.email).first().verification_code

    response = client.get("/api/user", headers=alice.headers)
    assert response.status_code == 200
    assert "verification_code" not in response.get_json()["user"]


# ---------------- 驗證碼 /api/verification/* ----------------

def test_send_verification_unregistered(client):
    response = client.post("/api/verification/send", json={"email": "nobody@example.com"})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "EMAIL_NOT_REGISTERED"


def test_send_verification_success(client, outbox):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    response = client.post("/api/verification/send", json={"email": "u@example.com"})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "VERIFICATION_CODE_SENT"
    assert len(outbox) == 2


def test_verify_wrong_code(client):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    response = client.post("/api/verification/check", json={"email": "u@example.com", "code": "000000x", "password": DEFAULT_PASSWORD})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "VERIFICATION_CODE_INCORRECT"


def test_verify_unknown_user(client):
    response = client.post("/api/verification/check", json={"email": "nobody@example.com", "code": "123456", "password": DEFAULT_PASSWORD})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "USER_NOT_FOUND"


def test_verify_expired_code(client, outbox, M, db_session):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    code = extract_code(outbox[0].body)

    user = M.User.query.filter_by(email="u@example.com").first()
    user.verification_code_expires = datetime(2000, 1, 1)
    db_session.commit()

    response = client.post("/api/verification/check", json={"email": "u@example.com", "code": code, "password": DEFAULT_PASSWORD})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "VERIFICATION_CODE_EXPIRED"


def test_verify_success_marks_user_verified(client, outbox, M, db_session):
    client.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    code = extract_code(outbox[0].body)

    response = client.post("/api/verification/check", json={"email": "u@example.com", "code": code, "password": DEFAULT_PASSWORD})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "VERIFICATION_SUCCESS"

    user = M.User.query.filter_by(email="u@example.com").first()
    assert user.is_verified is True
    assert user.verification_code is None


def test_verify_without_json_body(client):
    response = client.post("/api/verification/check", data="not json")
    assert response.status_code == 500
    assert response.get_json()["message_code"] == "VERIFICATION_FAILED"


# ---------------- 忘記密碼 POST /api/password/forgot ----------------

def test_forgot_password_sends_new_password(client, alice, outbox, M, db_session):
    response = client.post("/api/password/forgot", json={"email": alice.email})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "NEW_PASSWORD_SENT"

    # 信裡的新密碼可以登入，而且被標記成必須改密碼
    new_password = outbox[0].body.split(":", 1)[1].split()[0]
    assert len(new_password) == 8
    response = client.post("/api/auth", json={"email": alice.email, "password": new_password})
    assert response.status_code == 200
    assert M.User.query.filter_by(email=alice.email).first().must_change_password == 1


def test_forgot_password_mail_failure_keeps_old_password(client, alice, monkeypatch, M, db_session):
    def broken_mailer(email, new_password):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr("services.auth_service.send_new_password", broken_mailer)

    response = client.post("/api/password/forgot", json={"email": alice.email})
    assert response.status_code == 500
    assert response.get_json()["message_code"] == "RESET_FAILED"

    # 信沒寄出去，密碼和必須改密碼的標記都不變
    response = client.post("/api/auth", json={"email": alice.email, "password": alice.password})
    assert response.status_code == 200
    assert M.User.query.filter_by(email=alice.email).first().must_change_password == 0


@pytest.mark.parametrize("email, code", [
    ("bad", "INVALID_EMAIL_FORMAT"),
    ("nobody@example.com", "EMAIL_NOT_REGISTERED"),
])
def test_forgot_password_failures(client, email, code):
    response = client.post("/api/password/forgot", json={"email": email})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code


# ---------------- 重設密碼 POST /api/password/reset ----------------

def test_reset_password_requires_login(client):
    response = client.post("/api/password/reset", json={"email": "a@example.com", "password": "new-password"})
    assert response.status_code == 401


def test_reset_password_success(client, alice, M, db_session):
    response = client.post("/api/password/reset", headers=alice.headers, json={"email": alice.email, "password": "brand-new-pass"})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "PASSWORD_RESET_SUCCESS"

    response = client.post("/api/auth", json={"email": alice.email, "password": "brand-new-pass"})
    assert response.status_code == 200


def test_reset_password_too_short(client, alice):
    response = client.post("/api/password/reset", headers=alice.headers, json={"email": alice.email, "password": "short"})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "PASSWORD_TOO_SHORT"


def test_reset_password_email_must_be_string(client, alice):
    response = client.post("/api/password/reset", headers=alice.headers, json={"email": 123, "password": "brand-new-pass"})
    assert response.status_code == 422
    assert response.get_json()["message_code"] == "INVALID_USER_ID"


def test_reset_password_cannot_change_other_users_password(client, alice, bob):
    response = client.post("/api/password/reset", headers=alice.headers, json={"email": bob.email, "password": "hacked-by-alice"})
    assert response.status_code == 403
    assert response.get_json()["message_code"] == "FORBIDDEN"

    # bob 的密碼沒被改到
    assert client.post("/api/auth", json={"email": bob.email, "password": "hacked-by-alice"}).status_code != 200
    assert client.post("/api/auth", json={"email": bob.email, "password": bob.password}).status_code == 200


def test_reset_password_without_email_uses_login_identity(client, alice):
    response = client.post("/api/password/reset", headers=alice.headers, json={"password": "brand-new-pass"})
    assert response.status_code == 200
    assert client.post("/api/auth", json={"email": alice.email, "password": "brand-new-pass"}).status_code == 200


# ---------------- 沒設 MAIL_USERNAME（開發時開不寄信模式，常常不填寄件帳號） ----------------

@pytest.fixture
def client_without_mail_username(monkeypatch):
    """另外建一個沒設 MAIL_USERNAME 的 app（conftest 的 app 有設，測不到這個情況）"""
    from main import create_app
    from shared import env
    from utils.extensions import db, bcrypt

    monkeypatch.setattr(env, "mail_username", None)
    monkeypatch.setattr(env, "mail_password", None)
    monkeypatch.setattr(env, "mail_suppress_send", True)
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.extensions["mail"].suppress = True
    # create_app 裡的 bcrypt.init_app 會把 rounds 設回 12，改回測試用的 4
    bcrypt._log_rounds = 4

    yield flask_app.test_client()

    with flask_app.app_context():
        db.engine.dispose()


def test_register_without_mail_username_uses_default_sender(client_without_mail_username, outbox):
    response = client_without_mail_username.post("/api/register", json={"email": "u@example.com", "password": DEFAULT_PASSWORD})
    assert response.status_code == 201
    assert outbox[0].sender == "noreply@localhost"


def test_forgot_password_without_mail_username(client_without_mail_username, alice, outbox):
    response = client_without_mail_username.post("/api/password/forgot", json={"email": alice.email})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "NEW_PASSWORD_SENT"

    # 新密碼有存進資料庫，可以登入
    new_password = outbox[0].body.split(":", 1)[1].split()[0]
    response = client_without_mail_username.post("/api/auth", json={"email": alice.email, "password": new_password})
    assert response.status_code == 200
