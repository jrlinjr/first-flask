"""使用者資料、設定、病歷、徽章"""
import pytest


# ---------------- 取得使用者 GET /api/user ----------------

def test_endpoints_require_login(client):
    response = client.get("/api/user")
    assert response.status_code == 401


def test_get_user_returns_full_profile(client, alice):
    response = client.get("/api/user", headers=alice.headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "0"

    user = body["user"]
    assert user["id"] == alice.id
    assert user["email"] == alice.email
    assert user["account"] == "alice"
    assert user["status"] == "general"
    assert user["verified"] == 1
    assert user["must_change_password"] == 0
    # 沒存過邀請碼時，用 user id 算出 8 碼
    assert user["invite_code"] == "00012007"
    # 沒有任何子資料時都是預設值
    assert user["default"]["id"] == 0
    assert user["setting"]["unit_of_sugar"] == 0
    assert user["vip"]["level"] == 0
    assert user["a1c"] == {"message": "", "latest_value": 0.0, "latest_date": ""}


# ---------------- 更新使用者 PATCH /api/user ----------------

def test_update_user_fields(client, alice):
    payload = {
        "name": "Alice",
        "birthday": "1990-01-02",
        "height": 165.5,
        "weight": "55.5",
        "phone": "0912345678",
        "gender": 1,
        "address": "Taipei",
        "fcm_id": "fcm-token",
        "group": "A",
        "fb_id": "fb-1",
    }
    response = client.patch("/api/user", headers=alice.headers, json=payload)
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"

    user = client.get("/api/user", headers=alice.headers).get_json()["user"]
    assert user["name"] == "Alice"
    assert user["birthday"] == "1990-01-02"
    assert user["height"] == 165.5
    assert user["weight"] == 55.5
    assert user["phone"] == "0912345678"
    assert user["gender"] == 1
    assert user["address"] == "Taipei"
    assert user["fcm_id"] == "fcm-token"
    assert user["group"] == "A"
    assert user["fb_id"] == "fb-1"


def test_update_user_ignores_blank_email_and_zero_height(client, alice):
    client.patch("/api/user", headers=alice.headers, json={"height": 170})
    response = client.patch("/api/user", headers=alice.headers, json={"email": "   ", "height": 0})
    assert response.status_code == 200

    user = client.get("/api/user", headers=alice.headers).get_json()["user"]
    assert user["email"] == alice.email
    assert user["height"] == 170


def test_update_user_email_already_used(client, alice, bob):
    response = client.patch("/api/user", headers=alice.headers, json={"email": bob.email})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "EMAIL_ALREADY_USED"


def test_update_user_account_already_used(client, alice, bob):
    response = client.patch("/api/user", headers=alice.headers, json={"account": "bob"})
    assert response.status_code == 409
    assert response.get_json()["message_code"] == "ACCOUNT_ALREADY_USED"


# ---------------- 使用者設定 PATCH /api/user/setting ----------------

def test_update_user_setting(client, alice):
    response = client.patch("/api/user/setting", headers=alice.headers, json={
        "after_recording": True,
        "no_recording_for_a_day": 0,
        "over_max_or_under_min": 1,
        "after_meal": "yes",
        "unit_of_sugar": 1,
        "unit_of_weight": 0,
        "unit_of_height": 1,
    })
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"

    setting = client.get("/api/user", headers=alice.headers).get_json()["user"]["setting"]
    assert setting["id"] == 1
    assert setting["after_recording"] == 1
    assert setting["no_recording_for_a_day"] == 0
    assert setting["over_max_or_under_min"] == 1
    assert setting["after_meal"] == 1
    assert setting["unit_of_sugar"] == 1
    assert setting["unit_of_weight"] == 0
    assert setting["unit_of_height"] == 1


# ---------------- 病歷 GET / PATCH /api/user/medical ----------------

def test_get_medical_records_defaults(client, alice):
    response = client.get("/api/user/medical", headers=alice.headers)
    assert response.status_code == 200
    info = response.get_json()["medical_info"]
    assert info == {
        "id": 0, "user_id": alice.id, "diabetes_type": 0, "oad": 0,
        "insulin": 0, "anti_hypertensives": 0, "created_at": "", "updated_at": "",
    }


def test_update_and_get_medical_records(client, alice):
    response = client.patch("/api/user/medical", headers=alice.headers, json={
        "diabetes_type": 3, "oad": True, "insulin": False, "anti_hypertensives": 1,
    })
    assert response.status_code == 200

    info = client.get("/api/user/medical", headers=alice.headers).get_json()["medical_info"]
    assert info["id"] == 1
    assert info["diabetes_type"] == 3
    assert info["oad"] == 1
    assert info["insulin"] == 0
    assert info["anti_hypertensives"] == 1
    assert info["created_at"] != ""


def test_update_medical_ignores_out_of_range_type(client, alice):
    client.patch("/api/user/medical", headers=alice.headers, json={"diabetes_type": 2})
    client.patch("/api/user/medical", headers=alice.headers, json={"diabetes_type": 9})
    info = client.get("/api/user/medical", headers=alice.headers).get_json()["medical_info"]
    assert info["diabetes_type"] == 2


# ---------------- 徽章 PUT /api/user/badge ----------------

def test_update_badge_success(client, alice, M, db_session):
    response = client.put("/api/user/badge", headers=alice.headers, json={"badge": 5})
    assert response.status_code == 200
    assert M.UserDefault.query.filter_by(user_id=alice.id).first().badge == 5

    # 再更新一次是改同一筆
    client.put("/api/user/badge", headers=alice.headers, json={"Badge": 7})
    db_session.expire_all()
    rows = M.UserDefault.query.filter_by(user_id=alice.id).all()
    assert [row.badge for row in rows] == [7]


@pytest.mark.parametrize("payload, code", [
    ({}, "MISSING_BADGE_PARAMETER"),
    ({"badge": -1}, "BADGE_CANNOT_BE_NEGATIVE"),
    ({"badge": "abc"}, "BADGE_MUST_BE_INTEGER"),
])
def test_update_badge_validation(client, alice, payload, code):
    response = client.put("/api/user/badge", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code
