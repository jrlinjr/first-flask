"""好友：邀請碼、送出/接受/拒絕邀請、好友列表、好友分組"""
import pytest


def invite(client, sender, receiver_code, relation_type=1):
    return client.post("/api/friend/send", headers=sender.headers, json={"invite_code": receiver_code, "type": relation_type})


def invite_code_of(client, user):
    return client.get("/api/friend/code", headers=user.headers).get_json()["invite_code"]


# ---------------- 邀請碼 GET /api/friend/code ----------------

def test_get_invite_code_is_generated_once(client, alice, bob, M, db_session):
    response = client.get("/api/friend/code", headers=alice.headers)
    assert response.status_code == 200
    assert response.get_json()["invite_code"] == "00012007"
    assert invite_code_of(client, bob) == "00022014"

    # 第二次拿到同一組（已存進資料庫）
    assert invite_code_of(client, alice) == "00012007"
    assert db_session.get(M.User, alice.id).invite_code == "00012007"


# ---------------- 送出邀請 POST /api/friend/send ----------------

def test_send_invite_success_and_lists(client, alice, bob):
    response = invite(client, alice, invite_code_of(client, bob))
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"

    # bob 收到的邀請
    requests = client.get("/api/friend/requests", headers=bob.headers).get_json()["requests"]
    assert len(requests) == 1
    assert requests[0]["user"] == {"id": alice.id, "name": "", "account": "alice"}
    assert requests[0]["status"] == 0

    # alice 發出去的邀請結果
    results = client.get("/api/friend/results", headers=alice.headers).get_json()["results"]
    assert len(results) == 1
    assert results[0]["relation"] == {"id": bob.id, "name": "", "account": "bob"}


@pytest.mark.parametrize("payload, status, code", [
    ({}, 400, "MISSING_PARAMETERS"),
    ({"invite_code": "123"}, 400, "MISSING_PARAMETERS"),
    ({"invite_code": "123", "type": "x"}, 400, "PARAMETER_TYPE_ERROR"),
    ({"invite_code": "   ", "type": 1}, 400, "INVITE_CODE_EMPTY"),
    ({"invite_code": "99999999", "type": 1}, 404, "INVALID_INVITE_CODE"),
])
def test_send_invite_validation(client, alice, payload, status, code):
    response = client.post("/api/friend/send", headers=alice.headers, json=payload)
    assert response.status_code == status
    assert response.get_json()["message_code"] == code


def test_send_invite_to_self(client, alice):
    response = invite(client, alice, invite_code_of(client, alice))
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "CANNOT_INVITE_SELF"


def test_send_invite_when_already_friends(client, alice, bob):
    invite(client, alice, invite_code_of(client, bob))
    client.get("/api/friend/1/accept", headers=bob.headers)

    response = invite(client, alice, invite_code_of(client, bob))
    assert response.status_code == 409
    assert response.get_json()["message_code"] == "ALREADY_FRIENDS"


def test_send_duplicate_pending_invite_is_rejected(client, alice, bob, M, db_session):
    code = invite_code_of(client, bob)
    invite(client, alice, code)
    response = invite(client, alice, code)
    assert response.status_code == 409
    assert response.get_json()["message_code"] == "INVITATION_ALREADY_SENT"

    # 對方反過來邀請也一樣擋（雙向檢查）
    response = invite(client, bob, invite_code_of(client, alice))
    assert response.status_code == 409
    assert response.get_json()["message_code"] == "INVITATION_ALREADY_SENT"
    assert M.FriendResult.query.count() == 1

    # 不同類型的邀請不受影響
    assert invite(client, alice, code, relation_type=2).status_code == 200


def test_send_invite_again_after_rejected(client, alice, bob, M, db_session):
    invite(client, alice, invite_code_of(client, bob))
    client.get("/api/friend/1/refuse", headers=bob.headers)

    # 被拒絕後可以再邀請一次（雙方都可以）
    response = invite(client, bob, invite_code_of(client, alice))
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"
    assert [(r.user_id, r.status) for r in M.FriendResult.query.order_by(M.FriendResult.id).all()] == [(alice.id, 2), (bob.id, 0)]


# ---------------- 接受 / 拒絕 GET /api/friend/<id>/accept|refuse ----------------

def test_accept_invite_makes_both_friends(client, alice, bob):
    invite(client, alice, invite_code_of(client, bob))

    response = client.get("/api/friend/1/accept", headers=bob.headers)
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"

    alice_friends = client.get("/api/friend/list", headers=alice.headers).get_json()["friends"]
    bob_friends = client.get("/api/friend/list", headers=bob.headers).get_json()["friends"]
    assert [(f["id"], f["relation_type"], f["relation_type_name"], f["name"]) for f in alice_friends] == [(bob.id, 1, "親友團", "bob")]
    assert [(f["id"], f["relation_type"]) for f in bob_friends] == [(alice.id, 1)]

    # 已接受後，alice 那邊的結果標成已讀，不會再出現
    assert client.get("/api/friend/results", headers=alice.headers).get_json()["results"] == []

    # 再接受一次
    response = client.get("/api/friend/1/accept", headers=bob.headers)
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "ALREADY_ACCEPTED"


def test_accept_invite_not_found(client, alice, bob):
    invite(client, alice, invite_code_of(client, bob))
    # 只有被邀請的人可以接受
    response = client.get("/api/friend/1/accept", headers=alice.headers)
    assert response.status_code == 404
    assert response.get_json()["message_code"] == "INVITATION_NOT_FOUND"


def test_refuse_invite(client, alice, bob):
    invite(client, alice, invite_code_of(client, bob))

    response = client.get("/api/friend/1/refuse", headers=bob.headers)
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"
    assert client.get("/api/friend/requests", headers=bob.headers).get_json()["requests"] == []

    # 已處理過就找不到
    response = client.get("/api/friend/1/refuse", headers=bob.headers)
    assert response.status_code == 404

    # 被拒絕後不能再接受
    response = client.get("/api/friend/1/accept", headers=bob.headers)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "ALREADY_REJECTED"


def test_friend_list_empty(client, alice):
    response = client.get("/api/friend/list", headers=alice.headers)
    assert response.status_code == 200
    assert response.get_json()["friends"] == []


# ---------------- 好友分組 POST /api/friend、/api/friends/default ----------------

def test_add_friend_group(client, alice, M, db_session):
    response = client.post("/api/friend", headers=alice.headers, json={"name": "運動團", "relation_type": 2})
    assert response.status_code == 201
    assert M.Friend.query.filter_by(user_id=alice.id, name="運動團").count() == 1


@pytest.mark.parametrize("payload, status, code", [
    ({"name": "  "}, 400, "FRIEND_NAME_REQUIRED"),
    ({"name": "x", "relation_type": 5}, 400, "INVALID_RELATION_TYPE"),
    ({"name": "醫師團"}, 409, "FRIEND_ALREADY_EXISTS"),
])
def test_add_friend_group_validation(client, alice, payload, status, code):
    response = client.post("/api/friend", headers=alice.headers, json=payload)
    assert response.status_code == status
    assert response.get_json()["message_code"] == code


def test_recreate_default_groups(client, alice, M, db_session):
    # 註冊時已有 3 個預設分組，所以不會再加
    response = client.post("/api/friends/default", headers=alice.headers)
    assert response.status_code == 200
    assert response.get_json()["added_friends"] == []

    # 刪掉兩個分組後，會補回缺的
    for group in M.Friend.query.filter_by(user_id=alice.id).order_by(M.Friend.id).limit(2).all():
        db_session.delete(group)
    db_session.commit()

    response = client.post("/api/friends/default", headers=alice.headers)
    assert response.get_json()["added_friends"] == ["醫師團", "親友團"]


# ---------------- 解除好友 DELETE /api/friend/remove ----------------

def make_friends(client, sender, receiver, relation_type=1):
    invite(client, sender, invite_code_of(client, receiver), relation_type)
    invite_id = client.get("/api/friend/requests", headers=receiver.headers).get_json()["requests"][0]["id"]
    client.get(f"/api/friend/{invite_id}/accept", headers=receiver.headers)


def friend_ids(client, user):
    return [f["id"] for f in client.get("/api/friend/list", headers=user.headers).get_json()["friends"]]


def test_remove_friend(client, alice, bob, make_user, M, db_session):
    carol = make_user("carol@example.com", account="carol")
    make_friends(client, alice, bob)
    make_friends(client, alice, carol)
    group_count = M.Friend.query.count()

    # 第三人刪不到別人之間的關係
    response = client.delete("/api/friend/remove", headers=carol.headers, json={"ids[]": [bob.id]})
    assert response.status_code == 200
    assert response.get_json()["deleted_count"] == 0
    assert friend_ids(client, bob) == [alice.id]

    # 接受邀請產生兩筆記錄，但只算 1 個人；雙方的好友列表都清掉
    response = client.delete("/api/friend/remove", headers=alice.headers, json={"ids[]": [bob.id]})
    assert response.status_code == 200
    assert response.get_json()["deleted_count"] == 1
    assert friend_ids(client, alice) == [carol.id]
    assert friend_ids(client, bob) == []

    # 再刪一次沒有東西可刪
    response = client.delete("/api/friend/remove", headers=alice.headers, json={"ids[]": [bob.id]})
    assert response.get_json()["deleted_count"] == 0

    # 分組不受影響；解除後可以重新邀請
    assert M.Friend.query.count() == group_count
    assert invite(client, bob, invite_code_of(client, alice)).status_code == 200


@pytest.mark.parametrize("payload, code", [
    ({}, "FRIEND_ID_REQUIRED"),
    ({"ids[]": ["x"]}, "INVALID_FRIEND_ID"),
])
def test_remove_friends_validation(client, alice, payload, code):
    response = client.delete("/api/friend/remove", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code
