"""分享記錄、最新消息、整體行為（未登入、找不到路徑）"""
from datetime import datetime

import pytest


def make_friends(client, sender, receiver, relation_type=1):
    code = client.get("/api/friend/code", headers=receiver.headers).get_json()["invite_code"]
    client.post("/api/friend/send", headers=sender.headers, json={"invite_code": code, "type": relation_type})
    invite_id = client.get("/api/friend/requests", headers=receiver.headers).get_json()["requests"][0]["id"]
    client.get(f"/api/friend/{invite_id}/accept", headers=receiver.headers)


# ---------------- 分享 POST /api/share ----------------

def test_add_share_then_update(client, alice):
    client.post("/api/user/blood/sugar", headers=alice.headers, json={"sugar": 100})

    response = client.post("/api/share", headers=alice.headers, json={"type": 2, "id": 1, "relation_type": 1})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SHARE_SUCCESS"

    response = client.post("/api/share", headers=alice.headers, json={"type": "2", "id": "1", "relation_type": "1"})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "UPDATE_SHARE_SUCCESS"


@pytest.mark.parametrize("payload, code", [
    ({}, "PARAMETER_TYPE_ERROR"),
    ({"type": "x", "id": 1, "relation_type": 1}, "PARAMETER_TYPE_ERROR"),
    ({"type": 1, "id": 1, "relation_type": 3}, "INVALID_RELATION_TYPE"),
    ({"type": 4, "id": 1, "relation_type": 1}, "INVALID_TYPE"),
    ({"type": 1, "id": 0, "relation_type": 1}, "INVALID_RECORD_ID"),
])
def test_add_share_validation(client, alice, payload, code):
    response = client.post("/api/share", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code


# ---------------- 好友分享給我的 GET /api/share/<relation_type> ----------------

def test_get_shared_records_from_friend(client, alice, bob):
    make_friends(client, alice, bob, relation_type=1)
    client.post("/api/user/blood/sugar", headers=alice.headers, json={"sugar": 123, "timeperiod": 3, "recorded_at": "2025-01-02 08:00:00"})
    client.post("/api/share", headers=alice.headers, json={"type": 2, "id": 1, "relation_type": 1})

    response = client.get("/api/share/1", headers=bob.headers)
    assert response.status_code == 200
    records = response.get_json()["records"]
    assert len(records) == 1
    record = records[0]
    assert record["user"] == {"id": alice.id, "name": "", "email": alice.email, "account": "alice"}
    assert record["sugar"] == 123.0
    assert record["timeperiod"] == 3
    assert record["recorded_at"] == "2025-01-02 08:00:00"
    assert record["relation_type"] == 1

    # 不同分組看不到
    assert client.get("/api/share/0", headers=bob.headers).get_json()["records"] == []


def test_get_shared_records_without_friends(client, alice):
    response = client.get("/api/share/1", headers=alice.headers)
    assert response.status_code == 200
    assert response.get_json()["records"] == []


# ---------------- 最新消息 GET /api/news ----------------

def test_get_news(client, alice, M, db_session):
    db_session.add(M.News(member_id=alice.id, group=1, title="Hello", message="World",
                          created_at=datetime(2025, 1, 1), updated_at=datetime(2025, 1, 1)))
    db_session.add(M.News(member_id=alice.id, group=2, title="中文標題", message="中文內容",
                          created_at=datetime(2025, 2, 1), updated_at=datetime(2025, 2, 1)))
    db_session.commit()

    response = client.get("/api/news", headers=alice.headers)
    assert response.status_code == 200
    news = response.get_json()["news"]
    # 新的在前；含中文的標題/內容會被換成替代文字（原本程式刻意這樣寫）
    assert [(n["id"], n["title"], n["message"]) for n in news] == [
        (2, "Content 2", "Content 2"),
        (1, "Hello", "World"),
    ]
    assert news[0]["pushed_at"] == ""
    assert news[1]["created_at"] == "2025-01-01 00:00:00"


# ---------------- 整體行為 ----------------

@pytest.mark.parametrize("method, path", [
    ("get", "/api/user"), ("patch", "/api/user"), ("get", "/api/news"), ("get", "/api/friend/list"),
    ("post", "/api/user/blood/sugar"), ("delete", "/api/user/records"), ("get", "/api/share/1"),
    ("post", "/api/friends/default"),
])
def test_protected_endpoints_without_token(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing Authorization Header"


def test_invalid_token(client):
    response = client.get("/api/user", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 422


def test_unknown_path_returns_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"status": "1", "message": "Not Found", "message_code": "NOT_FOUND"}


def test_wrong_method_returns_405(client):
    response = client.put("/api/user")
    assert response.status_code == 405
    assert response.get_json()["message_code"] == "METHOD_NOT_ALLOWED"
    assert "PATCH" in response.headers["Allow"]
