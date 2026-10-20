"""分享端點（都要登入）"""
from flask import Blueprint, request, jsonify

from services.share_service import ShareService
from utils.api_response import error_body
from utils.decorators import login_required, handle_route_errors

share_bp = Blueprint("share", __name__)

# relation_type：0 醫師團、1 親友團、2 控糖團
VALID_RELATION_TYPES = [0, 1, 2]


@share_bp.post("/share")
@login_required
@handle_route_errors("Share failed", "SHARE_FAILED")
def add_share(email: str):
    """分享一筆記錄，body：{"type": 記錄類型, "id": 記錄 id, "relation_type": 分組}"""
    data = request.get_json(silent=True) or {}

    try:
        record_type = int(data.get("type"))
        record_id = int(data.get("id"))
        relation_type = int(data.get("relation_type"))
    except (ValueError, TypeError) as e:
        return jsonify(error_body(f"Parameter type error: {e}", "PARAMETER_TYPE_ERROR")), 400

    if relation_type not in VALID_RELATION_TYPES:
        return jsonify(error_body("relation_type must be 0(doctor), 1(family), or 2(friend)", "INVALID_RELATION_TYPE")), 400

    result, status = ShareService.add_share_record(email, record_type, record_id, relation_type)
    return jsonify(result), status


@share_bp.get("/share/<relation_type>")
@login_required
@handle_route_errors("Failed to get shared records", "GET_SHARED_RECORDS_FAILED")
def get_shared_records(relation_type, email: str):
    """好友分享給我的記錄"""
    result, status = ShareService.get_shared_records(email, relation_type)
    return jsonify(result), status
