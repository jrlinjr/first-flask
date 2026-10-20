"""最新消息端點（要登入）"""
from flask import Blueprint, jsonify

from services.news_service import NewsService
from utils.decorators import login_required, handle_route_errors

news_bp = Blueprint("news", __name__)


@news_bp.get("/news")
@login_required
@handle_route_errors("Failed to get news", "GET_NEWS_FAILED")
def get_news(email: str):
    """所有最新消息"""
    result, status = NewsService.get_news(email)
    return jsonify(result), status
