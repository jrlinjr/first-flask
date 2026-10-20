"""
帳號認證端點：註冊、登入、驗證碼、忘記 / 重設密碼

這幾支（除了 verification/check）原本就沒有 try/except，
出錯時交給 main.py 的全域錯誤處理回 500「系統錯誤」
（body 不是 JSON 這類 HTTP 錯誤則保留原本的 400 / 415）。
"""
from flask import Blueprint, request, jsonify

from services.auth_service import AuthService
from utils.api_response import error_body
from utils.decorators import handle_route_errors, login_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    """註冊"""
    data: dict = request.get_json(silent=True) or {}
    email: str = (data.get("email") or "").strip()
    password: str = data.get("password") or ""
    account = data.get("account") or None

    result, status = AuthService.register(email, password, account)
    return jsonify(result), status


@auth_bp.get("/register/check")
@handle_route_errors("Check failed", "CHECK_FAILED", error_details=True)
def check_register():
    """檢查 email 能不能註冊"""
    email = request.args.get("email", "").strip()
    if not email:
        # 原本的行為：status "1" 但 HTTP 200
        return jsonify(error_body("Email parameter cannot be empty", "EMAIL_REQUIRED")), 200

    result, status = AuthService.check_email(email)
    return jsonify(result), status


@auth_bp.post("/auth")
def login():
    """登入，成功回傳 JWT"""
    data = request.get_json(silent=True) or {}
    email: str = (data.get("email") or "").strip()
    password: str = (data.get("password") or "").strip()

    result, status = AuthService.login(email, password)
    return jsonify(result), status


@auth_bp.post("/verification/send")
def send_verification():
    """寄送驗證碼"""
    data: dict = request.get_json()
    email: str = data.get("email")

    result, status = AuthService.send_verification(email)
    return jsonify(result), status


@auth_bp.post("/verification/check")
@handle_route_errors("Verification failed", "VERIFICATION_FAILED", error_details=True)
def verify_code():
    """檢查驗證碼"""
    data: dict = request.get_json()
    email: str = data.get("email")
    code: str = data.get("code")

    result, status = AuthService.verify_code(email, code)
    return jsonify(result), status


@auth_bp.post("/password/forgot")
def forgot_password():
    """忘記密碼：寄新密碼到信箱"""
    email: str = request.json.get("email")

    result, status = AuthService.forgot_password(email)
    return jsonify(result), status


@auth_bp.post("/password/reset")
@login_required
def reset_password(email: str):
    """重設密碼（要登入）

    只能改登入者本人（JWT 身分）的密碼。
    body 的 email 可以不帶；有帶的話必須是登入者本人，不然回 403
    """
    requested_email = request.json.get("email")
    if requested_email is not None and not isinstance(requested_email, str):
        return jsonify(error_body("Invalid user identification", "INVALID_USER_ID")), 422

    new_password: str = request.json.get("password")
    result, status = AuthService.reset_password(email, new_password, requested_email)
    return jsonify(result), status
