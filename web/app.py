"""Flask web interface for Signal Lab - multi-platform promotion."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# ================= [경로 꼬임 방지 핵심 시스템] =================
# app.py의 위치와 상관없이 프로젝트 루트(E:\signal_lab)를 파이썬 검색 경로에 강제 주입
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # web 폴더의 상위 폴더

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# =============================================================

from flask import Flask, render_template, request, jsonify

from config.settings import settings
from database.db import SignalDatabase
from subscription.manager import SubscriptionManager

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
app.secret_key = settings.telegram_token or "signal-lab-secret-key"


def get_services():
    """Get database and subscription services."""
    db = SignalDatabase(settings.db_path)
    sub = SubscriptionManager(settings, db)
    return db, sub


@app.route("/")
def index():
    """Landing page."""
    db, sub = get_services()
    stats = db.revenue_stats()
    
    return render_template(
        "index.html",
        premium_price=settings.premium_price_krw,
        vip_price=settings.vip_price_krw,
        free_tickers=settings.free_tickers,
        total_tickers=len(settings.tickers),
        stats=stats,
    )


@app.route("/api/referral/<chat_id>")
def referral_link(chat_id):
    """Get referral link for a chat ID."""
    db, sub = get_services()
    link = sub.referral_link(int(chat_id))
    return jsonify({"link": link, "chat_id": chat_id})


@app.route("/api/stats")
def api_stats():
    """Get public statistics."""
    db, _ = get_services()
    stats = db.revenue_stats()
    
    public_stats = {
        "free_count": stats["free_count"],
        "premium_count": stats["premium_count"],
        "vip_count": stats["vip_count"],
        "total_subscribers": stats["free_count"] + stats["premium_count"] + stats["vip_count"],
    }
    
    return jsonify(public_stats)


@app.route("/share")
def share_page():
    """Share page with multiple platform options."""
    referral_code = request.args.get("ref", "")
    
    bot_username = settings.bot_username.lstrip("@")
    telegram_link = f"https://t.me/{bot_username}"
    
    if referral_code:
        telegram_link = f"https://t.me/{bot_username}?start={referral_code}"
    
    return render_template(
        "share.html",
        telegram_link=telegram_link,
        referral_code=referral_code,
        premium_price=settings.premium_price_krw,
        vip_price=settings.vip_price_krw,
        free_tickers=settings.free_tickers,
        bank_name=settings.bank_name,
        bank_account=settings.bank_account,
        bank_holder=settings.bank_holder,
        payment_contact=settings.payment_contact,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
