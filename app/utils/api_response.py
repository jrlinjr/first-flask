"""
標準化 API 回應格式處理器
確保所有 API 回應都有一致的結構，供前端正確處理
"""

from flask import jsonify
from typing import Any, Optional, Dict, Union
import traceback

class APIResponse:
    """標準化 API 回應處理器"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", message_code: str = "SUCCESS", status_code: int = 200) -> tuple:
        """
        成功回應格式
        
        Args:
            data: 返回的數據
            message: 成功訊息
            message_code: 訊息代碼
            status_code: HTTP 狀態碼
        
        Returns:
            (response, status_code) 元組
        """
        response = {
            "status": "0",  # 字串格式，保持與現有格式一致
            "message": message,
            "message_code": message_code
        }
        
        # 如果有數據，添加到回應中
        if data is not None:
            if isinstance(data, dict):
                # 如果 data 是字典，將其內容合併到回應中
                response.update(data)
            else:
                # 否則將 data 作為 data 欄位
                response["data"] = data
        
        return jsonify(response), status_code
    
    @staticmethod
    def error(message: str = "An error occurred", message_code: str = "ERROR", status_code: int = 400, details: Optional[Dict] = None) -> tuple:
        """
        錯誤回應格式
        
        Args:
            message: 錯誤訊息
            message_code: 錯誤代碼
            status_code: HTTP 狀態碼
            details: 額外的錯誤詳情
        
        Returns:
            (response, status_code) 元組
        """
        response = {
            "status": "1",  # 字串格式，保持與現有格式一致
            "message": message,
            "message_code": message_code
        }
        
        # 如果有額外詳情，添加到回應中
        if details:
            response.update(details)
        
        return jsonify(response), status_code
    
    @staticmethod
    def validation_error(message: str = "Validation failed", message_code: str = "VALIDATION_FAILED", field_errors: Optional[Dict] = None) -> tuple:
        """
        驗證錯誤回應格式
        
        Args:
            message: 錯誤訊息
            message_code: 錯誤代碼
            field_errors: 欄位驗證錯誤詳情
        
        Returns:
            (response, status_code) 元組
        """
        details = {}
        if field_errors:
            details["field_errors"] = field_errors
        
        return APIResponse.error(message, message_code, 422, details)
    
    @staticmethod
    def unauthorized(message: str = "Unauthorized", message_code: str = "UNAUTHORIZED") -> tuple:
        """
        未授權錯誤回應格式
        
        Returns:
            (response, status_code) 元組
        """
        return APIResponse.error(message, message_code, 401)
    
    @staticmethod
    def forbidden(message: str = "Forbidden", message_code: str = "FORBIDDEN") -> tuple:
        """
        禁止訪問錯誤回應格式
        
        Returns:
            (response, status_code) 元組
        """
        return APIResponse.error(message, message_code, 403)
    
    @staticmethod
    def not_found(message: str = "Resource not found", message_code: str = "NOT_FOUND") -> tuple:
        """
        資源不存在錯誤回應格式
        
        Returns:
            (response, status_code) 元組
        """
        return APIResponse.error(message, message_code, 404)
    
    @staticmethod
    def server_error(message: str = "Internal server error", message_code: str = "INTERNAL_ERROR", error_details: Optional[str] = None) -> tuple:
        """
        伺服器錯誤回應格式
        
        Args:
            message: 錯誤訊息
            message_code: 錯誤代碼
            error_details: 錯誤詳情 (用於調試)
        
        Returns:
            (response, status_code) 元組
        """
        details = {}
        if error_details:
            details["error_details"] = error_details
        
        return APIResponse.error(message, message_code, 500, details)
    
    @staticmethod
    def handle_exception(e: Exception, message: str = "An unexpected error occurred", message_code: str = "UNEXPECTED_ERROR") -> tuple:
        """
        處理例外並返回標準化錯誤回應
        
        Args:
            e: 例外對象
            message: 自定義錯誤訊息
            message_code: 錯誤代碼
        
        Returns:
            (response, status_code) 元組
        """
        # 獲取例外詳情用於調試
        error_details = str(e)
        
        # 記錄完整的 traceback 用於調試
        traceback.print_exc()
        
        return APIResponse.server_error(message, message_code, error_details)

# 常用的回應快捷方式
def success_response(data=None, message="Success", message_code="SUCCESS"):
    """成功回應快捷方式"""
    return APIResponse.success(data, message, message_code)

def error_response(message="Error", message_code="ERROR", status_code=400):
    """錯誤回應快捷方式"""
    return APIResponse.error(message, message_code, status_code)

def user_not_found():
    """用戶不存在錯誤"""
    return APIResponse.error("User not found", "USER_NOT_FOUND", 404)

def invalid_user_id():
    """無效用戶 ID 錯誤"""
    return APIResponse.validation_error("Invalid user identification", "INVALID_USER_ID")

def missing_auth():
    """缺少認證錯誤"""
    return APIResponse.unauthorized("Missing authorization header", "MISSING_AUTH_HEADER")

def invalid_auth():
    """無效認證錯誤"""
    return APIResponse.unauthorized("Invalid authorization header", "INVALID_AUTH_HEADER")

def auth_failed():
    """認證失敗錯誤"""
    return APIResponse.unauthorized("Authentication failed", "AUTH_FAILED")

def system_error():
    """系統錯誤"""
    return APIResponse.server_error("System error", "SYSTEM_ERROR")

# 前端開發者參考指南
API_RESPONSE_GUIDE = """
前端開發者 API 回應處理指南
==============================

1. 標準回應格式:
   所有 API 回應都包含以下欄位：
   - status: 字串 "0" (成功) 或 "1" (失敗)
   - message: 人類可讀的訊息
   - message_code: 機器可處理的錯誤代碼
   
   成功回應可能包含額外的數據欄位。

2. 成功回應範例:
   {
     "status": "0",
     "message": "Success",
     "message_code": "SUCCESS",
     "data": {...}
   }

3. 錯誤回應範例:
   {
     "status": "1",
     "message": "User not found",
     "message_code": "USER_NOT_FOUND"
   }

4. 前端處理建議:
   - 檢查 status 欄位判斷操作成功與否
   - 使用 message_code 進行程式邏輯處理
   - 顯示 message 給使用者
   - 根據 HTTP 狀態碼進行適當的錯誤處理

5. 常見 HTTP 狀態碼:
   - 200: 操作成功
   - 400: 請求參數錯誤
   - 401: 未授權 (需要登入)
   - 403: 禁止訪問
   - 404: 資源不存在
   - 422: 資料驗證失敗
   - 500: 伺服器內部錯誤

6. 常見 message_code:
   - SUCCESS: 操作成功
   - USER_NOT_FOUND: 用戶不存在
   - INVALID_USER_ID: 無效的用戶 ID
   - MISSING_AUTH_HEADER: 缺少認證標頭
   - INVALID_AUTH_HEADER: 無效的認證標頭
   - AUTH_FAILED: 認證失敗
   - VALIDATION_FAILED: 資料驗證失敗
   - SYSTEM_ERROR: 系統錯誤
   - INTERNAL_ERROR: 內部錯誤
"""