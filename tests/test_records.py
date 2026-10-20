"""健康記錄：血糖、血壓、體重、飲食、日記、最新記錄、刪除、A1c、照護"""
from datetime import date

import pytest


# ---------------- 血糖 POST /api/user/blood/sugar ----------------

def test_add_blood_sugar(client, alice, M, db_session):
    response = client.post("/api/user/blood/sugar", headers=alice.headers, json={
        "sugar": 120.5, "timeperiod": 2, "recorded_at": "2025-01-02 08:30:00", "drug": 1, "exercise": 0,
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["message_code"] == "SUCCESS"
    assert body["new_record_id"] == 1

    diary = db_session.get(M.Diary, 1)
    assert diary.type == "blood_sugar"
    assert diary.sugar == 120.5
    assert diary.timeperiod == 2
    assert diary.drug == 1
    assert diary.recorded_at.strftime("%Y-%m-%d %H:%M:%S") == "2025-01-02 08:30:00"


@pytest.mark.parametrize("payload, code", [
    ({}, "SUGAR_REQUIRED"),
    ({"sugar": 0}, "INVALID_BLOOD_SUGAR"),
    ({"sugar": 1001}, "INVALID_BLOOD_SUGAR"),
    ({"sugar": "abc"}, "BLOOD_SUGAR_MUST_BE_NUMBER"),
    ({"sugar": 100, "recorded_at": "2025/01/02"}, "INVALID_RECORDED_AT_FORMAT"),
])
def test_add_blood_sugar_validation(client, alice, payload, code):
    response = client.post("/api/user/blood/sugar", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code


# ---------------- 血壓 POST /api/user/blood/pressure ----------------

def test_add_blood_pressure(client, alice, M, db_session):
    response = client.post("/api/user/blood/pressure", headers=alice.headers, json={
        "Systolic": 120, "diastolic": "80", "pulse": 70, "recorded_at": "2025-01-02 09:00:00",
    })
    assert response.status_code == 201
    assert response.get_json()["new_record_id"] == 1

    diary = db_session.get(M.Diary, 1)
    assert (diary.type, diary.systolic, diary.diastolic, diary.pulse) == ("blood_pressure", 120, 80, 70)


@pytest.mark.parametrize("payload, code", [
    ({"systolic": 120, "diastolic": 80}, "BP_HR_PARAMETERS_REQUIRED"),
    ({"systolic": 0, "diastolic": 80, "pulse": 70}, "INVALID_BP_HR"),
    ({"systolic": "abc", "diastolic": 80, "pulse": 70}, "BP_HR_MUST_BE_NUMBER"),
    ({"systolic": -5, "diastolic": 80, "pulse": 70}, "INVALID_BP_HR"),
    ({"systolic": 120, "diastolic": 80, "pulse": 70, "recorded_at": "bad"}, "INVALID_RECORDED_AT_FORMAT"),
])
def test_add_blood_pressure_validation(client, alice, payload, code):
    response = client.post("/api/user/blood/pressure", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code


# ---------------- 體重 POST /api/user/weight ----------------

def test_add_weight_calculates_bmi(client, alice, M, db_session):
    response = client.post("/api/user/weight", headers=alice.headers, json={"weight": 72.25, "recorded_at": "2025-01-03 07:00:00"})
    assert response.status_code == 200
    assert response.get_json()["new_record_id"] == 1

    diary = db_session.get(M.Diary, 1)
    assert diary.type == "weight"
    assert diary.weight == 72.25
    # 使用者資料沒填身高，用預設 170 公分算 BMI
    assert diary.bmi == 25.0
    assert diary.body_fat == 0.0


def test_add_weight_uses_user_height_for_bmi(client, alice, M, db_session):
    client.patch("/api/user", headers=alice.headers, json={"height": 160})

    response = client.post("/api/user/weight", headers=alice.headers, json={"weight": 64})
    assert response.status_code == 200
    # 64 / 1.6² = 25.0
    assert db_session.get(M.Diary, 1).bmi == 25.0


def test_add_weight_unreasonable_user_height_uses_default(client, alice, M, db_session):
    # PATCH /api/user 不檢查身高範圍，存了不合理的值也不能讓新增體重失敗
    client.patch("/api/user", headers=alice.headers, json={"height": 500})

    response = client.post("/api/user/weight", headers=alice.headers, json={"weight": 72.25})
    assert response.status_code == 200
    # 改用預設 170 公分：72.25 / 1.7² = 25.0
    assert db_session.get(M.Diary, 1).bmi == 25.0


@pytest.mark.parametrize("payload, code", [
    ({}, "WEIGHT_REQUIRED"),
    ({"weight": 0}, "INVALID_WEIGHT"),
    ({"weight": 501}, "INVALID_WEIGHT"),
    ({"weight": "abc"}, "PARAMETER_TYPE_ERROR"),
    ({"weight": 60, "recorded_at": "bad"}, "INVALID_RECORDED_AT_FORMAT"),
])
def test_add_weight_validation(client, alice, payload, code):
    response = client.post("/api/user/weight", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code


def test_add_weight_without_json_body(client, alice):
    response = client.post("/api/user/weight", headers=alice.headers, data="not json")
    assert response.status_code == 500
    assert response.get_json()["message"].startswith("新增體重失敗")


# ---------------- 飲食 POST /api/user/diet ----------------

def test_add_diet_record(client, alice, M, db_session):
    response = client.post("/api/user/diet", headers=alice.headers, json={
        "description": "早餐", "meal": 1, "tag": ["蛋", "牛奶"], "image": 0,
        "lat": 25.03, "lng": 121.56, "recorded_at": "2025-01-02 07:30:00",
    })
    assert response.status_code == 201
    assert response.get_json() == {"status": "0", "message": "Success", "message_code": "SUCCESS", "image_url": ""}

    diary = db_session.get(M.Diary, 1)
    assert diary.type == "diet"
    assert diary.description == "早餐"
    assert diary.meal == 1


def test_add_diet_record_bad_time_falls_back_to_now(client, alice):
    response = client.post("/api/user/diet", headers=alice.headers, json={"description": "x", "recorded_at": "bad", "tag": "單一"})
    assert response.status_code == 201


# ---------------- 日記 GET /api/user/diary ----------------

def test_get_diary_with_diet_records(client, alice):
    client.post("/api/user/diet", headers=alice.headers, json={
        "description": "早餐", "meal": 1, "tag": ["蛋"], "lat": 25.03, "lng": 121.56, "recorded_at": "2025-01-02 07:30:00",
    })
    client.post("/api/user/diet", headers=alice.headers, json={
        "description": "午餐", "meal": 2, "tag": [], "recorded_at": "2025-01-03 12:00:00",
    })

    response = client.get("/api/user/diary", headers=alice.headers)
    assert response.status_code == 200
    diary = response.get_json()["diary"]
    # 新的在前
    assert [d["description"] for d in diary] == ["午餐", "早餐"]
    assert diary[1]["tag"] == ["蛋"]
    assert diary[1]["location"] == {"lat": "25.03", "lng": "121.56"}
    assert diary[0]["location"] == {"lat": "None", "lng": "None"}

    response = client.get("/api/user/diary?date=2025-01-02", headers=alice.headers)
    assert [d["description"] for d in response.get_json()["diary"]] == ["早餐"]


def test_get_diary_invalid_date(client, alice):
    response = client.get("/api/user/diary?date=2025/01/02", headers=alice.headers)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "INVALID_DATE_FORMAT"


def test_get_diary_with_blood_sugar_record(client, alice):
    # 血糖記錄的 location 是 NULL，回傳空字串的 lat / lng
    client.post("/api/user/blood/sugar", headers=alice.headers, json={"sugar": 100})
    response = client.get("/api/user/diary", headers=alice.headers)
    assert response.status_code == 200
    diary = response.get_json()["diary"]
    assert [d["type"] for d in diary] == ["blood_sugar"]
    assert diary[0]["location"] == {"lat": "", "lng": ""}


# ---------------- 最新記錄 POST /api/user/records ----------------

def test_get_user_records_latest_values(client, alice):
    client.post("/api/user/blood/sugar", headers=alice.headers, json={"sugar": 100, "timeperiod": 1, "recorded_at": "2025-01-01 08:00:00"})
    client.post("/api/user/blood/sugar", headers=alice.headers, json={"sugar": 130, "timeperiod": 2, "recorded_at": "2025-01-02 08:00:00"})
    client.post("/api/user/blood/pressure", headers=alice.headers, json={"systolic": 120, "diastolic": 80, "pulse": 70, "recorded_at": "2025-01-01 09:00:00"})
    client.post("/api/user/weight", headers=alice.headers, json={"weight": 60, "recorded_at": "2025-01-01 10:00:00"})

    response = client.post("/api/user/records", headers=alice.headers, json={})
    assert response.status_code == 200
    body = response.get_json()
    assert body["blood_sugars"] == {"sugar": 130.0}
    assert body["blood_pressures"] == {"systolic": 120, "diastolic": 80, "pulse": 70}
    assert body["weights"] == {"weight": 60.0}

    # 指定時段
    body = client.post("/api/user/records", headers=alice.headers, json={"diet": 1}).get_json()
    assert body["blood_sugars"] == {"sugar": 100.0}


def test_get_user_records_invalid_diet(client, alice):
    response = client.post("/api/user/records", headers=alice.headers, json={"diet": "abc"})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "DIET_MUST_BE_INTEGER"


# ---------------- 刪除記錄 DELETE /api/user/records ----------------

def test_delete_user_records_only_own(client, alice, bob, M, db_session):
    client.post("/api/user/blood/sugar", headers=alice.headers, json={"sugar": 100})  # id 1
    client.post("/api/user/weight", headers=alice.headers, json={"weight": 60})       # id 2
    client.post("/api/user/blood/sugar", headers=bob.headers, json={"sugar": 110})    # id 3

    # 字典格式 + 混了 bob 的記錄
    response = client.delete("/api/user/records", headers=alice.headers, json={
        "deleteObject": {"blood_sugars": [1, 3], "weights": ["2"]},
    })
    assert response.status_code == 200
    assert response.get_json()["deleted_count"] == 2
    assert [d.id for d in M.Diary.query.all()] == [3]


@pytest.mark.parametrize("payload, code", [
    ({}, "INVALID_DELETE_IDS"),
    ({"deleteObject": []}, "INVALID_DELETE_IDS"),
    ({"deleteObject": ["a"]}, "INVALID_ID_FORMAT"),
])
def test_delete_user_records_validation(client, alice, payload, code):
    response = client.delete("/api/user/records", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == code


# ---------------- 糖化血色素 /api/user/a1c ----------------

def test_get_a1c_records_empty(client, alice):
    response = client.get("/api/user/a1c", headers=alice.headers)
    assert response.status_code == 200
    assert response.get_json()["a1cs"] == []


def test_get_a1c_records(client, alice, M, db_session):
    db_session.add(M.A1cRecord(user_id=alice.id, a1cs=6.5, record_date=date(2025, 1, 1)))
    db_session.add(M.A1cRecord(user_id=alice.id, a1cs=7.1, record_date=date(2025, 3, 1)))
    db_session.commit()

    response = client.get("/api/user/a1c", headers=alice.headers)
    assert response.status_code == 200
    records = response.get_json()["a1cs"]
    assert [(r["a1cs"], r["record_date"]) for r in records] == [("7.1", "2025-03-01"), ("6.5", "2025-01-01")]


def test_add_a1c_out_of_range(client, alice):
    response = client.post("/api/user/a1c", headers=alice.headers, json={"a1c": 2, "date": "2025-01-01"})
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "INVALID_HBA1C"


def test_add_a1c(client, alice, M, db_session):
    response = client.post("/api/user/a1c", headers=alice.headers, json={"a1c": 6.5, "date": "2025-01-01"})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"

    # 同一天再送一次是更新，不會多一筆
    response = client.post("/api/user/a1c", headers=alice.headers, json={"a1c": 7.2, "date": "2025-01-01"})
    assert response.status_code == 200
    records = M.A1cRecord.query.all()
    assert [(r.a1cs, r.record_date) for r in records] == [(7.2, date(2025, 1, 1))]

    # 使用者資料裡的最新 A1c 也要讀得到
    a1c = client.get("/api/user", headers=alice.headers).get_json()["user"]["a1c"]
    assert a1c["latest_value"] == 7.2
    assert a1c["latest_date"].startswith("2025-01-01")


# ---------------- 照護 /api/user/care ----------------

def test_get_care_records_empty(client, alice):
    response = client.get("/api/user/care", headers=alice.headers)
    assert response.status_code == 200
    assert response.get_json()["cares"] == []


def test_add_care_record(client, alice, M, db_session):
    response = client.post("/api/user/care", headers=alice.headers, json={"care_data": " 量血壓 "})
    assert response.status_code == 200
    assert response.get_json()["message_code"] == "SUCCESS"

    # 同樣內容再送一次只更新時間，不會多一筆
    client.post("/api/user/care", headers=alice.headers, json={"care_data": "量血壓"})
    assert [(r.user_id, r.care_data) for r in M.CareRecord.query.all()] == [(alice.id, "量血壓")]


@pytest.mark.parametrize("payload", [{}, {"care_data": "   "}, {"care_data": 123}])
def test_add_care_record_requires_data(client, alice, payload):
    response = client.post("/api/user/care", headers=alice.headers, json=payload)
    assert response.status_code == 400
    assert response.get_json()["message_code"] == "CARE_DATA_REQUIRED"


def test_get_care_records_with_data(client, alice, bob, M, db_session):
    # A1c 資料不會混進照護記錄
    db_session.add(M.A1cRecord(user_id=alice.id, a1cs=6.5, record_date=date(2025, 1, 1)))
    db_session.commit()
    client.post("/api/user/care", headers=alice.headers, json={"care_data": "量血壓"})
    client.post("/api/user/care", headers=alice.headers, json={"care_data": "回診"})
    client.post("/api/user/care", headers=bob.headers, json={"care_data": "bob 的記錄"})

    response = client.get("/api/user/care", headers=alice.headers)
    assert response.status_code == 200
    cares = response.get_json()["cares"]
    # 新的在前，只看得到自己的
    assert [c["cares"] for c in cares] == ["回診", "量血壓"]
    assert all(c["user_id"] == alice.id for c in cares)
