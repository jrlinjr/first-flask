"""
controller 共用的裝飾器

原本每支 route 都重複寫「取 JWT 身分 → 檢查是不是字串 → try/except 回 500」，
現在統一用這兩個裝飾器處理：

    @friend_bp.get("/friend/list")
    @login_required                                   # 1. 驗 JWT，email 放進 kwargs
    @handle_route_errors("Failed to get friends list", "GET_FRIENDS_LIST_FAILED")  # 2. 出錯回 500
    def get_friend_list(email: str):
        result, status = FriendService.get_friend_list(email)
        return jsonify(result), status
"""
import functools
import traceback

from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from utils.api_response import error_body
from utils.logger import logger


def login_required(func):
    """需要登入的端點：驗證 JWT，再把登入者的 email 放進 kwargs["email"]

    - 沒帶 token / token 無效 → 由 flask_jwt_extended 直接回 401 / 422
    - token 的身分不是 email 字串 → 回 422 INVALID_USER_ID
    """

    @functools.wraps(func)
    @jwt_required()
    def wrapper(*args, **kwargs):
        email = get_jwt_identity()
        if not isinstance(email, str) or not email.strip():
            return jsonify(error_body("Invalid user identification", "INVALID_USER_ID")), 422

        kwargs["email"] = email
        return func(*args, **kwargs)

    return wrapper


def handle_route_errors(message: str, message_code: str | None = None, append_error: bool = False, error_details: bool = False):
    """包住 controller 的端點：裡面一旦出錯，就記 log 並回 500

    回傳格式：{"status": "1", "message": message, "message_code": message_code}
    - message_code=None   → 不帶 message_code 欄位
    - append_error=True   → message 後面接上錯誤內容，例如 "新增體重失敗: ..."
    - error_details=True  → 多一個 error_details 欄位放錯誤內容
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"端點 {func.__name__} 發生錯誤：{e}")
                logger.error(traceback.format_exc())

                body = {"status": "1", "message": message}
                if append_error:
                    body["message"] = f"{message}: {e}"
                if message_code:
                    body["message_code"] = message_code
                if error_details and str(e):
                    body["error_details"] = str(e)
                return jsonify(body), 500

        return wrapper

    return decorator
