"""
最新消息

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
from models.user import User
from models.news import News
from utils.api_response import success_body, error_body
from utils.converters import safe_datetime_str
from utils.logger import logger


def _safe_news_text(text, empty_default: str, news_id: int) -> str:
    """消息文字的安全處理

    - 空的 → empty_default
    - 含中文等非 ASCII 字元 → "Content {id}"（原本程式刻意避免回傳中文，原因待確認）
    - 其他原樣回傳
    """
    if not text:
        return empty_default
    try:
        text.encode("ascii")
        return text
    except UnicodeEncodeError:
        return f"Content {news_id}"


class NewsService:

    @staticmethod
    def get_news(email: str):
        """所有最新消息，新的在前"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            news_records = News.query.order_by(News.created_at.desc()).all()

            news_list = []
            for news in news_records:
                news_list.append({
                    "id": news.id,
                    "member_id": news.member_id,
                    "group": news.group,
                    "title": _safe_news_text(news.title, f"News {news.id}", news.id),
                    "message": _safe_news_text(news.message, "Content available", news.id),
                    "pushed_at": safe_datetime_str(news.pushed_at),
                    "created_at": safe_datetime_str(news.created_at),
                    "updated_at": safe_datetime_str(news.updated_at),
                })

            return success_body("News retrieved successfully", "SUCCESS", news=news_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得最新消息失敗：{e}")
            return error_body("Failed to get news", "GET_NEWS_FAILED"), 500
