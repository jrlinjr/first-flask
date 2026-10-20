"""好友端點：邀請碼、邀請、好友列表、好友分組（都要登入）"""
from flask import Blueprint, request, jsonify

from services.friend_service import FriendService
from utils.api_response import error_body
from utils.decorators import login_required, handle_route_errors

friend_bp = Blueprint("friend", __name__)


# ---------------- 邀請 ----------------

@friend_bp.get("/friend/code")
@login_required
@handle_route_errors("Failed to get invite code", "GET_INVITE_CODE_FAILED")
def get_friend_invite_code(email: str):
    """取得我的好友邀請碼"""
    result, status = FriendService.get_friend_invite_code(email)
    return jsonify(result), status


@friend_bp.post("/friend/send")
@login_required
@handle_route_errors("Failed to send invitation", "SEND_INVITATION_FAILED")
def send_friend_invite(email: str):
    """用對方的邀請碼送出好友邀請"""
    data = request.get_json(silent=True) or {}
    invite_code = data.get("invite_code")
    relation_type = data.get("type")

    if invite_code is None or relation_type is None:
        return jsonify(error_body("Missing required parameters", "MISSING_PARAMETERS")), 400

    try:
        relation_type = int(relation_type)
    except (ValueError, TypeError):
        return jsonify(error_body("Parameter type error", "PARAMETER_TYPE_ERROR")), 400

    result, status = FriendService.send_friend_invite(email, invite_code, relation_type)
    return jsonify(result), status


@friend_bp.get("/friend/requests")
@login_required
@handle_route_errors("Failed to get invitation list", "GET_INVITATIONS_FAILED")
def get_friend_requests(email: str):
    """我收到的邀請"""
    result, status = FriendService.get_friend_requests(email)
    return jsonify(result), status


@friend_bp.get("/friend/results")
@login_required
@handle_route_errors("Failed to get invitation results", "GET_INVITE_RESULTS_FAILED")
def get_friend_results(email: str):
    """我發出的邀請結果（待處理或未讀）"""
    result, status = FriendService.get_friend_results(email)
    return jsonify(result), status


@friend_bp.get("/friend/<int:invite_id>/accept")
@login_required
@handle_route_errors("Failed to accept invitation", "ACCEPT_INVITATION_FAILED")
def accept_friend_invite(invite_id: int, email: str):
    """接受邀請"""
    result, status = FriendService.accept_friend_invite(email, invite_id)
    return jsonify(result), status


@friend_bp.get("/friend/<int:invite_id>/refuse")
@login_required
@handle_route_errors("Failed to refuse invitation", "REFUSE_INVITATION_FAILED")
def refuse_friend_invite(invite_id: int, email: str):
    """拒絕邀請"""
    result, status = FriendService.refuse_friend_invite(email, invite_id)
    return jsonify(result), status


@friend_bp.get("/friend/list")
@login_required
@handle_route_errors("Failed to get friends list", "GET_FRIENDS_LIST_FAILED")
def get_friend_list(email: str):
    """好友列表"""
    result, status = FriendService.get_friend_list(email)
    return jsonify(result), status


# ---------------- 好友分組 ----------------

@friend_bp.post("/friend")
@login_required
@handle_route_errors("Failed to add friend", "ADD_FRIEND_FAILED")
def add_friend(email: str):
    """新增好友分組"""
    data = request.get_json(silent=True) or {}
    result, status = FriendService.add_friend(email, data.get("name"), data.get("relation_type", 0))
    return jsonify(result), status


@friend_bp.delete("/friend/remove")
@login_required
@handle_route_errors("Failed to remove friend", "REMOVE_FRIEND_FAILED")
def remove_friends(email: str):
    """解除好友關係，body：{"ids[]": [好友的 user id, ...]}"""
    data = request.get_json(silent=True) or {}
    result, status = FriendService.remove_friends(email, data.get("ids[]", []))
    return jsonify(result), status


@friend_bp.post("/friends/default")
@login_required
@handle_route_errors("Failed to create default friends", "CREATE_DEFAULT_FRIENDS_FAILED")
def create_default_friends(email: str):
    """補上缺少的預設分組"""
    result, status = FriendService.create_default_friends_for_user(email)
    return jsonify(result), status
