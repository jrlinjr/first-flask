"""
好友：邀請碼、送出 / 接受 / 拒絕邀請、好友列表、好友分組

兩張表別搞混：
- FriendResult：真正的好友關係 / 邀請（user_id 邀請 relation_id，status 0 待處理、1 接受、2 拒絕）
- Friend：使用者自己的「分組」名稱（醫師團、親友團、控糖團…）

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from models.user import User
from models.friend import Friend
from models.friendresult import FriendResult
from utils.api_response import success_body, error_body
from utils.code_generator import generate_invite_code
from utils.extensions import db
from utils.logger import logger
from utils.time_utils import now_taiwan

# 關係類型
RELATION_TYPE_NAMES = {0: "醫師團", 1: "親友團", 2: "控糖團"}

# 新使用者預設會有的三個分組（註冊時、/friends/default 都會用到）
DEFAULT_FRIEND_GROUPS = [
    {"name": "醫師團", "relation_type": 0},
    {"name": "親友團", "relation_type": 1},
    {"name": "控糖團", "relation_type": 2},
]

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_time(value) -> str:
    """時間轉字串，沒有值回空字串"""
    if value:
        return value.strftime(DATETIME_FORMAT)
    return ""


class FriendService:

    @staticmethod
    def get_friend_list(email: str):
        """好友列表：雙向關係中 status=1（已接受）的對象，同一人只列一次"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            # 預先載入雙方的使用者資料，避免 N+1 查詢
            friend_relations = (
                FriendResult.query
                .options(
                    joinedload(FriendResult.user),
                    joinedload(FriendResult.relation_user),
                )
                .filter(
                    db.or_(
                        FriendResult.user_id == user.id,
                        FriendResult.relation_id == user.id,
                    ),
                    FriendResult.status == 1,
                )
                .all()
            )

            friends_list = []
            seen_friend_ids = set()

            for relation in friend_relations:
                # 我是邀請方 → 對方是 relation_user；我是被邀請方 → 對方是 user
                if relation.user_id == user.id:
                    friend_user = relation.relation_user
                else:
                    friend_user = relation.user

                # 對方不存在或已經加過就跳過
                if not friend_user or friend_user.id in seen_friend_ids:
                    continue
                seen_friend_ids.add(friend_user.id)

                friends_list.append({
                    "id": friend_user.id,
                    "name": friend_user.name or friend_user.account or f"User {friend_user.id}",
                    "relation_type": relation.type,
                    "relation_type_name": RELATION_TYPE_NAMES.get(relation.type, "general"),
                    "email": friend_user.email or "",
                    "created_at": relation.created_at.isoformat() if relation.created_at else "",
                })

            return success_body(friends=friends_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得好友列表失敗：{e}")
            return error_body("Failed to get friends list", "GET_FRIENDS_LIST_FAILED"), 500

    @staticmethod
    def get_friend_results(email: str):
        """
        我發出的邀請結果
        只回傳：1) 待處理（status=0）或 2) 未讀（read=0）的；已接受且已讀的不再回傳
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            sent_invites = (
                FriendResult.query
                .options(joinedload(FriendResult.relation_user))
                .filter(
                    FriendResult.user_id == user.id,
                    db.or_(
                        FriendResult.status == 0,  # 待處理
                        FriendResult.read == 0,    # 未讀
                    ),
                )
                .order_by(FriendResult.created_at.desc())
                .all()
            )

            results_list = []
            for invite in sent_invites:
                invited_user = invite.relation_user
                if not invited_user:
                    continue

                results_list.append({
                    "id": invite.id,
                    "user_id": invite.user_id,
                    "relation_id": invite.relation_id,
                    "type": invite.type,
                    "status": invite.status,
                    "read": invite.read,
                    "created_at": _format_time(invite.created_at),
                    "updated_at": _format_time(invite.updated_at),
                    "relation": {
                        "id": invited_user.id,
                        "name": invited_user.name or "",
                        "account": invited_user.account or "",
                    },
                })

            return success_body("success", "SUCCESS", results=results_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得邀請結果失敗：{e}")
            return error_body("system error", "SYSTEM_ERROR"), 500

    @staticmethod
    def get_friend_requests(email: str):
        """我收到、還沒處理（status=0）的邀請"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            friend_requests = (
                FriendResult.query
                .options(joinedload(FriendResult.user))
                .filter_by(relation_id=user.id, status=0)
                .order_by(FriendResult.created_at.desc())
                .all()
            )

            requests_list = []
            for invite in friend_requests:
                from_user = invite.user
                # 邀請者不存在就跳過
                if not from_user:
                    continue

                requests_list.append({
                    "id": invite.id,
                    "user_id": invite.user_id,
                    "relation_id": invite.relation_id,
                    "type": invite.type,
                    "status": invite.status,
                    "read": invite.read,
                    "created_at": _format_time(invite.created_at),
                    "updated_at": _format_time(invite.updated_at),
                    "user": {
                        "id": from_user.id,
                        "name": from_user.name or "",
                        "account": from_user.account or "",
                    },
                })

            return success_body(requests=requests_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得收到的邀請失敗：{e}")
            return error_body("Failed to get invitation list", "GET_INVITATIONS_FAILED"), 500

    @staticmethod
    def get_friend_invite_code(email: str):
        """取得我的邀請碼；還沒有就產生並存起來"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if user.invite_code:
                return success_body(invite_code=user.invite_code), 200

            invite_code = generate_invite_code(user.id)

            try:
                user.invite_code = invite_code
                db.session.commit()
            except SQLAlchemyError:
                # 存檔失敗也照樣回傳算出來的邀請碼
                db.session.rollback()

            return success_body(invite_code=invite_code), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 取得邀請碼失敗：{e}")
            return error_body("Failed to get invite code", "GET_INVITE_CODE_FAILED"), 500

    @staticmethod
    def send_friend_invite(email: str, invite_code: str, relation_type: int):
        """
        用對方的邀請碼送出好友邀請

        Args:
            email: 送出邀請的人
            invite_code: 對方的邀請碼
            relation_type: 0 醫師團、1 親友團、2 控糖團
        """
        try:
            if not invite_code or not str(invite_code).strip():
                return error_body("Invite code cannot be empty", "INVITE_CODE_EMPTY"), 400

            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            invited_user = User.query.filter_by(invite_code=str(invite_code).strip()).first()
            if not invited_user:
                return error_body("Please enter a valid friend invite code", "INVALID_INVITE_CODE"), 404

            if user.id == invited_user.id:
                return error_body("Cannot invite yourself", "CANNOT_INVITE_SELF"), 400

            # 檢查雙向是否已有同類型、還有效的關係（1 已接受、0 等待中）
            # 被拒絕（status=2）的不擋，可以再邀請一次
            existing_statuses = {
                relation.status
                for relation in FriendResult.query.filter(
                    db.or_(
                        db.and_(
                            FriendResult.user_id == user.id,
                            FriendResult.relation_id == invited_user.id,
                        ),
                        db.and_(
                            FriendResult.user_id == invited_user.id,
                            FriendResult.relation_id == user.id,
                        ),
                    ),
                    FriendResult.type == relation_type,
                    FriendResult.status.in_([0, 1]),
                ).all()
            }

            if 1 in existing_statuses:
                return error_body("Already friends", "ALREADY_FRIENDS"), 409
            if 0 in existing_statuses:
                return error_body("Invitation already sent", "INVITATION_ALREADY_SENT"), 409

            db.session.add(FriendResult(
                user_id=user.id,
                relation_id=invited_user.id,
                type=relation_type,
                status=0,  # 待處理
                read=0,    # 未讀
            ))
            db.session.commit()

            return success_body("Friend invitation sent successfully", "SUCCESS"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 送出好友邀請失敗：{e}")
            return error_body("Failed to send invitation", "SEND_INVITATION_FAILED"), 500

    @staticmethod
    def is_already_friend(user_id, target_user_id, relation_type) -> bool:
        """兩人是否已經是指定類型的好友（目前沒有地方呼叫）"""
        try:
            existing_friendship = FriendResult.query.filter(
                db.or_(
                    db.and_(
                        FriendResult.user_id == user_id,
                        FriendResult.relation_id == target_user_id,
                        FriendResult.type == relation_type,
                        FriendResult.status == 1,
                    ),
                    db.and_(
                        FriendResult.user_id == target_user_id,
                        FriendResult.relation_id == user_id,
                        FriendResult.type == relation_type,
                        FriendResult.status == 1,
                    ),
                )
            ).first()
            return existing_friendship is not None

        except Exception as e:
            logger.error(f"檢查好友關係失敗：{e}")
            return False

    @staticmethod
    def accept_friend_invite(email: str, invite_id: int):
        """接受邀請（只有被邀請的人可以接受），並建立反向的好友記錄"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            invite = FriendResult.query.filter_by(id=invite_id, relation_id=user.id).first()
            if not invite:
                return error_body("Invitation not found", "INVITATION_NOT_FOUND"), 404

            if invite.status == 1:
                return success_body("Friend invitation already accepted", "ALREADY_ACCEPTED"), 200
            elif invite.status == 2:
                return error_body("Invitation was already rejected", "ALREADY_REJECTED"), 400

            invite.status = 1
            invite.read = 1
            invite.updated_at = now_taiwan()

            # 反向關係不存在才建立
            existing_reverse = FriendResult.query.filter_by(
                user_id=user.id,
                relation_id=invite.user_id,
            ).first()

            if not existing_reverse:
                db.session.add(FriendResult(
                    user_id=user.id,
                    relation_id=invite.user_id,
                    type=invite.type,
                    status=1,
                    read=1,
                    created_at=now_taiwan(),
                    updated_at=now_taiwan(),
                ))

            db.session.commit()
            return success_body("Friend invitation accepted successfully", "SUCCESS"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 接受好友邀請失敗：{e}")
            return error_body("Failed to accept invitation", "ACCEPT_INVITATION_FAILED"), 500

    @staticmethod
    def refuse_friend_invite(email: str, invite_id: int):
        """拒絕還在等待中的邀請"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            invite = FriendResult.query.filter_by(id=invite_id, relation_id=user.id, status=0).first()
            if not invite:
                return error_body("Invitation not found or already processed", "INVITATION_NOT_FOUND"), 404

            invite.status = 2
            invite.read = 1
            invite.updated_at = now_taiwan()
            db.session.commit()

            return success_body("Invitation rejected successfully", "SUCCESS"), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 拒絕好友邀請失敗：{e}")
            return error_body("Failed to refuse invitation", "REFUSE_INVITATION_FAILED"), 500

    @staticmethod
    def add_friend(email: str, friend_name: str, relation_type: int = 0):
        """新增一個好友「分組」（Friend 表）"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if not friend_name or not friend_name.strip():
                return error_body("Friend name cannot be empty", "FRIEND_NAME_REQUIRED"), 400

            if relation_type not in [0, 1, 2]:
                return error_body("Invalid relation_type parameter", "INVALID_RELATION_TYPE"), 400

            existing_friend = Friend.query.filter_by(user_id=user.id, name=friend_name.strip()).first()
            if existing_friend:
                return error_body("Friend already exists", "FRIEND_ALREADY_EXISTS"), 409

            db.session.add(Friend(
                user_id=user.id,
                name=friend_name.strip(),
                relation_type=relation_type,
                created_at=now_taiwan(),
                updated_at=now_taiwan(),
            ))
            db.session.commit()
            return success_body(), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增好友分組失敗：{e}")
            return error_body("Failed to add friend", "ADD_FRIEND_FAILED"), 500

    @staticmethod
    def remove_friends(email: str, friend_ids):
        """解除好友關係

        friend_ids 是好友的 user id（GET /friend/list 回的 id），
        刪掉我跟這些人之間雙向的 FriendResult（不分類型），Friend 分組不動。
        deleted_count 回實際被解除關係的人數（接受邀請會產生兩筆記錄，用人數比較直覺）
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if not isinstance(friend_ids, list) or not friend_ids:
                return error_body("Please provide friend ID to remove", "FRIEND_ID_REQUIRED"), 400

            try:
                int_ids = []
                for friend_id in friend_ids:
                    int_ids.append(int(friend_id))
            except (ValueError, TypeError):
                return error_body("Invalid friend ID format", "INVALID_FRIEND_ID"), 400

            relations = FriendResult.query.filter(
                db.or_(
                    db.and_(
                        FriendResult.user_id == user.id,
                        FriendResult.relation_id.in_(int_ids),
                    ),
                    db.and_(
                        FriendResult.user_id.in_(int_ids),
                        FriendResult.relation_id == user.id,
                    ),
                ),
            ).all()

            # 記下對方的 user id，同一人有兩筆記錄只算一次
            removed_user_ids = set()
            for relation in relations:
                other_id = relation.relation_id if relation.user_id == user.id else relation.user_id
                removed_user_ids.add(other_id)
                db.session.delete(relation)
            db.session.commit()

            return success_body(deleted_count=len(removed_user_ids)), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 解除好友關係失敗：{e}")
            return error_body("Failed to remove friend", "REMOVE_FRIEND_FAILED"), 500

    @staticmethod
    def create_default_friends_for_user(email: str):
        """補上缺少的預設分組（醫師團、親友團、控糖團）"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            existing_types = []
            for friend in Friend.query.filter_by(user_id=user.id).all():
                existing_types.append(friend.relation_type)

            added_friends = []
            for group in DEFAULT_FRIEND_GROUPS:
                # 只補還沒有的關係類型
                if group["relation_type"] not in existing_types:
                    db.session.add(Friend(
                        user_id=user.id,
                        name=group["name"],
                        relation_type=group["relation_type"],
                        created_at=now_taiwan(),
                        updated_at=now_taiwan(),
                    ))
                    added_friends.append(group["name"])

            db.session.commit()
            return success_body(added_friends=added_friends), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 建立預設分組失敗：{e}")
            return error_body("Failed to create default friends", "CREATE_DEFAULT_FRIENDS_FAILED"), 500
