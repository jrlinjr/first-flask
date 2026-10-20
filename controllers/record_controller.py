"""健康記錄端點：血糖、血壓、體重、飲食、日記、A1c、照護（都要登入）"""
from flask import Blueprint, request, jsonify

from services.a1c_service import A1cService
from services.record_service import RecordService
from utils.api_response import error_body
from utils.decorators import login_required, handle_route_errors

record_bp = Blueprint("record", __name__)


# ---------------- 血糖 / 血壓 / 體重 / 飲食 ----------------

@record_bp.post("/user/blood/sugar")
@login_required
@handle_route_errors("Failed to add blood sugar record", "ADD_BLOOD_SUGAR_FAILED")
def add_blood_sugar(email: str):
    """新增血糖記錄"""
    data = request.get_json(silent=True) or {}
    result, status = RecordService.add_blood_sugar(
        email=email,
        sugar=data.get("sugar"),
        timeperiod=data.get("timeperiod"),
        recorded_at=data.get("recorded_at"),
        drug=data.get("drug"),
        exercise=data.get("exercise"),
    )
    return jsonify(result), status


@record_bp.post("/user/blood/pressure")
@login_required
@handle_route_errors("Failed to add blood pressure record", "ADD_BLOOD_PRESSURE_FAILED")
def add_blood_pressure(email: str):
    """新增血壓記錄（參數名稱大小寫開頭都接受）"""
    data = request.get_json(silent=True) or {}
    systolic = data.get("Systolic") or data.get("systolic")
    diastolic = data.get("Diastolic") or data.get("diastolic")
    pulse = data.get("Pulse") or data.get("pulse")
    recorded_at = data.get("Recorded_at") or data.get("recorded_at")

    if systolic is None or diastolic is None or pulse is None:
        return jsonify(error_body("Blood pressure and heart rate parameters cannot be empty", "BP_HR_PARAMETERS_REQUIRED")), 400

    result, status = RecordService.add_blood_pressure(
        email=email,
        systolic=systolic,
        diastolic=diastolic,
        pulse=pulse,
        recorded_at=recorded_at,
    )
    return jsonify(result), status


@record_bp.post("/user/weight")
@login_required
@handle_route_errors("新增體重失敗", append_error=True)
def add_weight(email: str):
    """新增體重記錄"""
    weight = request.json.get("weight")
    result, status = RecordService.add_weight(email, weight, recorded_at=request.json.get("recorded_at"))
    return jsonify(result), status


@record_bp.post("/user/diet")
@login_required
@handle_route_errors("Failed to add diet record", "ADD_DIET_FAILED")
def add_diet_record(email: str):
    """新增飲食記錄"""
    data = request.get_json(silent=True) or {}
    result, status = RecordService.add_diet_record(
        email=email,
        description=data.get("description", ""),
        meal=data.get("meal", 0),
        tag=data.get("tag", []),
        image=data.get("image", 0),
        lat=data.get("lat", None),
        lng=data.get("lng", None),
        recorded_at=data.get("recorded_at", None),
    )
    return jsonify(result), status


# ---------------- 查詢 / 刪除 ----------------

@record_bp.get("/user/diary")
@login_required
@handle_route_errors("Failed to get diary entries", "GET_DIARY_FAILED")
def get_diary_entries(email: str):
    """取得日記，可用 ?date=YYYY-MM-DD 篩選"""
    date = request.args.get("date")
    result, status = RecordService.get_diary_entries(email, date)
    return jsonify(result), status


@record_bp.post("/user/records")
@login_required
@handle_route_errors("Failed to get health records", "GET_HEALTH_RECORDS_FAILED")
def get_user_records(email: str):
    """取得最新的血糖、血壓、體重；body 的 diet 是時段"""
    data = request.get_json(silent=True) or {}
    result, status = RecordService.get_user_records(email, data.get("diet"))
    return jsonify(result), status


@record_bp.delete("/user/records")
@login_required
@handle_route_errors("Failed to delete health records", "DELETE_HEALTH_RECORDS_FAILED")
def delete_user_records(email: str):
    """批次刪除健康記錄"""
    data = request.get_json(silent=True) or {}
    result, status = RecordService.delete_user_records(email, data.get("deleteObject", []))
    return jsonify(result), status


# ---------------- A1c / 照護 ----------------

@record_bp.post("/user/a1c")
@login_required
@handle_route_errors("新增 A1C 失敗", append_error=True)
def add_a1c(email: str):
    """新增 A1c 記錄"""
    a1c = request.json.get("a1c")
    date = request.json.get("date")
    result, status = A1cService.add_a1c(email, a1c, date)
    return jsonify(result), status


@record_bp.get("/user/a1c")
@login_required
@handle_route_errors("Failed to get A1C records", "GET_A1C_FAILED")
def get_a1c_records(email: str):
    """取得 A1c 記錄"""
    result, status = A1cService.get_a1c_records(email)
    return jsonify(result), status


@record_bp.post("/user/care")
@login_required
@handle_route_errors("Failed to add care record", "ADD_CARE_FAILED")
def add_care_record(email: str):
    """新增照護記錄"""
    care_data = request.json.get("care_data")
    result, status = A1cService.add_care_record(email, care_data)
    return jsonify(result), status


@record_bp.get("/user/care")
@login_required
@handle_route_errors("Failed to get care records", "GET_CARE_FAILED")
def get_care_records(email: str):
    """取得照護記錄"""
    result, status = A1cService.get_care_records(email)
    return jsonify(result), status
