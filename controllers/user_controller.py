"""使用者端點：個人資料、通知設定、病歷、徽章（都要登入）"""
from flask import Blueprint, request, jsonify

from services.user_service import UserService
from utils.api_response import error_body
from utils.decorators import login_required, handle_route_errors

user_bp = Blueprint("user", __name__)


@user_bp.get("/user")
@login_required
@handle_route_errors("System error", "SYSTEM_ERROR")
def get_user(email: str):
    """取得使用者完整資訊"""
    result, status = UserService.get_user(email)
    return jsonify(result), status


@user_bp.patch("/user")
@login_required
@handle_route_errors("Update failed", "UPDATE_FAILED", append_error=True)
def update_user(email: str):
    """更新使用者資料"""
    user_data = request.get_json(silent=True) or {}
    result, status = UserService.update_user(email, user_data)
    return jsonify(result), status


@user_bp.patch("/user/setting")
@login_required
@handle_route_errors("更新設定失敗", append_error=True)
def update_user_setting(email: str):
    """更新通知 / 單位設定"""
    setting_data = request.get_json(silent=True) or {}
    result, status = UserService.update_user_setting(email, setting_data)
    return jsonify(result), status


@user_bp.get("/user/medical")
@login_required
@handle_route_errors("Failed to get medical records", "GET_MEDICAL_RECORDS_FAILED")
def get_medical_records(email: str):
    """取得病歷"""
    result, status = UserService.get_medical_records(email)
    return jsonify(result), status


@user_bp.patch("/user/medical")
@login_required
@handle_route_errors("Failed to update medical records", "UPDATE_MEDICAL_RECORDS_FAILED")
def update_medical_records(email: str):
    """更新病歷"""
    medical_data = request.get_json(silent=True) or {}
    result, status = UserService.update_medical_records(email, medical_data)
    return jsonify(result), status


@user_bp.put("/user/badge")
@login_required
@handle_route_errors("Failed to update badge", "UPDATE_BADGE_FAILED")
def update_user_badge(email: str):
    """更新徽章數"""
    data = request.get_json(silent=True) or {}

    # 兩種參數名稱都接受
    badge = data.get("Badge") or data.get("badge")
    if badge is None:
        return jsonify(error_body("Missing badge parameter", "MISSING_BADGE_PARAMETER")), 400

    result, status = UserService.update_user_badge(email, badge)
    return jsonify(result), status
