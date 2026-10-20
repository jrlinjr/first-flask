from controllers.auth_controller import auth_bp
from controllers.user_controller import user_bp
from controllers.record_controller import record_bp
from controllers.friend_controller import friend_bp
from controllers.share_controller import share_bp
from controllers.news_controller import news_bp

# 別人用 from controllers import * 時，只會拿到名單裡這些名字
__all__ = ["auth_bp", "user_bp", "record_bp", "friend_bp", "share_bp", "news_bp"]
