"""Signal Lab interactive Telegram bot for subscription and monetization."""

from __future__ import annotations

import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.settings import settings
from database.db import SignalDatabase
from reports.daily_report import DailyReportGenerator
from subscription.manager import SubscriptionManager
from utils.logger import setup_logger

logger = logging.getLogger(__name__)

# Rate limiting for security (prevent spam/abuse)
_rate_limit_store: dict[int, list[float]] = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 30
MAX_REQUESTS_PER_HOUR = 100


def _check_rate_limit(chat_id: int) -> bool:
    """Check if user is within rate limits. Returns True if allowed."""
    now = time.time()
    timestamps = _rate_limit_store[chat_id]
    
    # Remove timestamps older than 1 hour
    timestamps[:] = [t for t in timestamps if now - t < 3600]
    
    # Check hourly limit
    if len(timestamps) >= MAX_REQUESTS_PER_HOUR:
        return False
    
    # Check minute limit
    minute_ago = now - 60
    recent_count = sum(1 for t in timestamps if t > minute_ago)
    if recent_count >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    # Add current timestamp
    timestamps.append(now)
    return True


def _get_disclaimer_footer() -> str:
    """Legal disclaimer footer for all messages."""
    return (
        "\n\n──────────\n"
        "⚠️ <b>투자 경고</b>\n"
        "이 정보는 투자 자문이 아닙니다. 모든 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다. "
        "과거 성과가 미래 수익을 보장하지 않습니다. 손실 가능성을 충분히 고려하십시오."
    )


def _get_services() -> tuple[SignalDatabase, SubscriptionManager, DailyReportGenerator]:
    db = SignalDatabase(settings.db_path)
    sub = SubscriptionManager(settings, db)
    report = DailyReportGenerator(settings, db)
    return db, sub, report


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or update.effective_message is None:
        return

    # Rate limiting check
    if not _check_rate_limit(chat.id):
        await update.effective_message.reply_text("⚠️ 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")
        return

    referred_by: int | None = None
    if context.args:
        ref_code = context.args[0].strip().upper()
        referrer = db.get_subscriber_by_referral_code(ref_code)
        if referrer and referrer.chat_id != chat.id:
            referred_by = referrer.chat_id

    sub.subscribe_free(chat.id, user.username if user else None, referred_by=referred_by)

    if referred_by:
        sub.apply_referral(context.args[0], chat.id)

    tier = sub.effective_tier(chat.id)
    await update.effective_message.reply_text(
        "🚀 <b>Signal Lab</b>에 오신 것을 환영합니다!\n\n"
        "미국 주식 자동 매수/매도 시그널 서비스입니다.\n\n"
        f"현재 등급: <b>{tier}</b>\n"
        f"무료 종목: {', '.join(settings.free_tickers)}\n\n"
        "📌 <b>자주 쓰는 명령</b>\n"
        "/premium — 요금제 안내\n"
        "/trial — 3일 무료 체험\n"
        "/pay — 결제 방법\n"
        "/invite — 친구 추천 (7일 추가)\n"
        "/share — 친구에게 공유\n"
        "/leaderboard — 추천 랭킹\n"
        "/status — 지금 시장 상태\n"
        "/help — 전체 명령어"
        + _get_disclaimer_footer(),
        parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        "📖 <b>Signal Lab 명령어</b>\n\n"
        "/start — 시작 + 무료 가입\n"
        "/premium — 요금제 (FREE/PREMIUM/VIP)\n"
        "/trial — 3일 무료 체험\n"
        "/pay — 결제 링크\n"
        "/invite — 내 추천 링크\n"
        "/share — 친구에게 공유\n"
        "/leaderboard — 추천 랭킹\n"
        "/checkin — 일일 출석 보상\n"
        "/status — RSI/MACD 현재 상태\n"
        "/signals — 최근 시그널\n"
        "/backtest — 성과 (PREMIUM+)\n"
        "/vip 코드 — VIP 활성화\n"
        "/unsubscribe — 구독 해지\n\n"
        "👑 관리자: /admin_stats /confirm_payment /grant_premium /grant_vip"
        + _get_disclaimer_footer(),
        parse_mode="HTML",
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or update.effective_message is None:
        return

    sub.subscribe_free(chat.id, user.username if user else None)
    await update.effective_message.reply_text(
        f"✅ 무료 구독 활성화\n"
        f"종목: {', '.join(settings.free_tickers)}\n"
        f"주 {settings.free_weekly_signal_limit}건 RSI 시그널\n\n"
        f"더 많은 시그널 → /premium",
        parse_mode="HTML",
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    if sub.unsubscribe(chat.id):
        await update.effective_message.reply_text("구독 해지 완료. 다시 이용: /start")
    else:
        await update.effective_message.reply_text("활성 구독이 없습니다.")


async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or update.effective_message is None:
        return

    if context.args:
        code = context.args[0]
        if sub.validate_premium_code(code):
            sub.subscribe_premium(chat.id, user.username if user else None)
            await update.effective_message.reply_text(
                "⭐ <b>PREMIUM 활성화!</b>\n\n"
                f"전체 종목 + MACD + 일일 리포트\n"
                f"유효기간: {settings.premium_duration_days}일",
                parse_mode="HTML",
            )
            return
        await update.effective_message.reply_text("❌ 유효하지 않은 코드입니다.")
        return

    await update.effective_message.reply_text(sub.pricing_message(), parse_mode="HTML")


async def cmd_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or update.effective_message is None:
        return

    if not context.args:
        await update.effective_message.reply_text(
            f"👑 <b>VIP</b> — ₩{settings.vip_price_krw:,}/월\n\n"
            f"Confluence 강력 시그널 + 최우선 알림\n\n"
            f"결제: /pay\n"
            f"코드 입력: /vip VIP코드",
            parse_mode="HTML",
        )
        return

    if sub.validate_vip_code(context.args[0]):
        sub.subscribe_vip(chat.id, user.username if user else None)
        await update.effective_message.reply_text(
            "👑 <b>VIP 활성화!</b>\n\n"
            "모든 시그널 + Confluence + 최우선 알림",
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text("❌ 유효하지 않은 VIP 코드입니다.")


async def cmd_trial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or update.effective_message is None:
        return

    result = sub.start_trial(chat.id, user.username if user else None)
    if result is None:
        await update.effective_message.reply_text("이미 무료 체험을 사용하셨습니다.\n/pay 로 결제해 주세요.")
        return

    await update.effective_message.reply_text(
        f"🎁 <b>{settings.trial_days}일 PREMIUM 무료 체험 시작!</b>\n\n"
        f"전체 종목 + MACD 시그널 + 일일 리포트\n"
        f"체험 후 자동 FREE 전환 → /pay 로 유지",
        parse_mode="HTML",
    )


async def cmd_pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        sub.pay_message(),
        parse_mode="HTML",
        disable_web_page_preview=False,
    )


async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    sub.subscribe_free(chat.id)
    link = sub.referral_link(chat.id)
    count = db.referral_count(chat.id)

    await update.effective_message.reply_text(
        f"🔗 <b>내 추천 링크</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"친구 1명 가입 시 <b>{settings.referral_bonus_days}일 PREMIUM</b> 추가!\n"
        f"현재 추천: {count}명",
        parse_mode="HTML",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, report_gen = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    tickers = sub.allowed_tickers(chat.id)
    message = report_gen.generate(tickers=tickers)
    tier = sub.effective_tier(chat.id)
    await update.effective_message.reply_text(
        f"등급: <b>{tier}</b>\n\n{message}",
        parse_mode="HTML",
    )


async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    signals = db.get_recent_signals(limit=10)
    allowed = set(sub.allowed_tickers(chat.id))
    tier = sub.effective_tier(chat.id)

    lines = [f"🔔 <b>최근 시그널</b> (등급: {tier})\n"]
    count = 0
    for sig in signals:
        if sig.ticker not in allowed:
            continue
        if not sub.can_receive_strategy(chat.id, sig.strategy):
            continue
        lines.append(
            f"{sig.signal_date} <b>{sig.ticker}</b> {sig.signal_type} [{sig.strategy}] ${sig.price}"
        )
        count += 1

    if count == 0:
        lines.append("표시할 시그널이 없습니다.")
    if tier == "FREE":
        used = db.get_weekly_signal_count(chat.id)
        lines.append(f"\n이번 주 수신: {used}/{settings.free_weekly_signal_limit}건")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    if not sub.is_premium(chat.id):
        await update.effective_message.reply_text("PREMIUM 이상 전용입니다.\n/trial 또는 /premium")
        return

    rows = db.get_latest_backtest_results()
    if not rows:
        await update.effective_message.reply_text("백테스트 데이터 없음. 관리자에게 문의하세요.")
        return

    lines = ["📊 <b>백테스트 성과 TOP</b>\n"]
    sorted_rows = sorted(rows, key=lambda r: r["win_rate"], reverse=True)[:8]
    for row in sorted_rows:
        lines.append(
            f"<b>{row['ticker']}</b> [{row['strategy']}]\n"
            f"  승률 {row['win_rate']:.1f}% | 평균 {row['avg_return_pct']:+.2f}%\n"
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    top_referrers = db.get_top_referrers(limit=10)
    if not top_referrers:
        await update.effective_message.reply_text("아직 추천 데이터가 없습니다.")
        return

    lines = ["🏆 <b>추천 리더보드</b>\n\n"]
    for idx, (username, count) in enumerate(top_referrers, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        display_name = username if username else f"User_{idx}"
        lines.append(f"{medal} {display_name}: {count}명 추천")

    lines.append(f"\n💡 친구 추천 시 {settings.referral_bonus_days}일 PREMIUM 추가!\n/invite")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_share(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    # Rate limiting check
    if not _check_rate_limit(chat.id):
        await update.effective_message.reply_text("⚠️ 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")
        return

    link = sub.referral_link(chat.id)
    count = sub.get_subscriber(chat.id)
    referral_count = 0 if count is None else 0
    
    try:
        referral_count = count.referral_count if hasattr(count, 'referral_count') else 0
    except:
        pass

    share_message = (
        "🚀 <b>Signal Lab - 미국 주식 자동 시그널</b>\n\n"
        "• RSI/MACD 기반 실시간 매수/매도 시그널\n"
        "• 무료로 시작 (SPY, QQQ)\n"
        "• PREMIUM: 전체 종목 + MACD + 일일 리포트\n"
        "• VIP: Confluence 강력 시그널\n\n"
        f"🔗 가입: {link}\n\n"
        "지금 바로 시작하세요! 📈"
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    # Multi-platform share buttons
    keyboard = [
        [
            InlineKeyboardButton("📱 텔레그램", url=f"https://t.me/share/url?url={link}&text=Signal Lab - 미국 주식 자동 시그널 봇! 무료로 시작하세요: "),
            InlineKeyboardButton("🐦 트위터/X", url=f"https://twitter.com/intent/tweet?text=Signal Lab - 미국 주식 자동 시그널 봇! 무료로 시작하세요: &url={link}")
        ],
        [
            InlineKeyboardButton("📘 페이스북", url=f"https://www.facebook.com/sharer/sharer.php?u={link}"),
            InlineKeyboardButton("💬 카카오톡", url=f"https://share.kakao.com/t?url={link}")
        ],
        [
            InlineKeyboardButton("📷 인스타그램", url=f"https://www.instagram.com/"),
            InlineKeyboardButton("🔗 링크 복사", callback_data="copy_link")
        ],
        [InlineKeyboardButton("🏆 리더보드", callback_data="leaderboard")],
        [InlineKeyboardButton("💰 요금제", callback_data="premium")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        f"📤 <b>다양한 플랫폼에서 공유</b>\n\n"
        f"아래 버튼을 클릭하여 친구에게 공유하세요!\n\n"
        f"현재 추천: {referral_count}명\n"
        f"추천 1명당 {settings.referral_bonus_days}일 PREMIUM 추가!\n\n"
        f"내 링크: <code>{link}</code>"
        + _get_disclaimer_footer(),
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    # Rate limiting check
    if not _check_rate_limit(chat.id):
        await update.effective_message.reply_text("⚠️ 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")
        return

    result = db.record_check_in(chat.id)
    
    if result["bonus"] > 0:
        bonus_msg = f"\n🎉 연속 보너스: +{result['bonus']} 포인트!"
    else:
        bonus_msg = ""
    
    await update.effective_message.reply_text(
        f"✅ <b>출석 완료!</b>\n\n"
        f"연속 출석: {result['streak']}일\n"
        f"총 출석: {result['total']}회\n"
        f"포인트: {result['points']}점 (+10){bonus_msg}\n\n"
        f"💡 포인트로 PREMIUM 기간 연장 가능 (추후 업데이트)"
        + _get_disclaimer_footer(),
        parse_mode="HTML",
    )


async def cmd_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    if not sub.is_admin(chat.id):
        await update.effective_message.reply_text("관리자 전용입니다.")
        return

    stats = db.revenue_stats()
    await update.effective_message.reply_text(
        f"📊 <b>수익 대시보드</b>\n\n"
        f"👥 구독자: FREE {stats['free_count']} | ⭐ PREMIUM {stats['premium_count']} | 👑 VIP {stats['vip_count']}\n"
        f"🎁 체험 중: {stats['active_trials']}명\n"
        f"🔗 추천 가입: {stats['referral_count']}건\n\n"
        f"💰 이번 달 결제: ₩{stats['month_revenue_krw']:,}\n"
        f"💰 누적 결제: ₩{stats['total_revenue_krw']:,}\n"
        f"📈 예상 MRR: ₩{stats['estimated_mrr_krw']:,}/월\n\n"
        f"📊 <b>성과 지표</b>\n"
        f"📈 전환율: {stats['conversion_rate']}%\n"
        f"💵 평균 LTV: ₩{stats['avg_ltv_krw']:,}\n"
        f"📉 이탈률: {stats['churn_rate']}%",
        parse_mode="HTML",
    )


async def cmd_admin_grant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    if not sub.is_admin(chat.id):
        await update.effective_message.reply_text("관리자 전용입니다.")
        return

    if not context.args:
        await update.effective_message.reply_text("사용법: /grant_premium CHAT_ID")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Chat ID는 숫자입니다.")
        return

    sub.subscribe_premium(target_id)
    await update.effective_message.reply_text(f"✅ {target_id} PREMIUM 부여 완료")


async def cmd_admin_grant_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    if not sub.is_admin(chat.id):
        return

    if not context.args:
        await update.effective_message.reply_text("사용법: /grant_vip CHAT_ID")
        return

    target_id = int(context.args[0])
    sub.subscribe_vip(target_id)
    await update.effective_message.reply_text(f"👑 {target_id} VIP 부여 완료")


async def cmd_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, sub, _ = _get_services()
    chat = update.effective_chat
    if chat is None or update.effective_message is None:
        return

    if not sub.is_admin(chat.id):
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "사용법: /confirm_payment CHAT_ID PREMIUM|VIP [메모]"
        )
        return

    target_id = int(context.args[0])
    tier = context.args[1].upper()
    note = " ".join(context.args[2:]) if len(context.args) > 2 else "admin confirmed"

    if tier not in ("PREMIUM", "VIP"):
        await update.effective_message.reply_text("등급: PREMIUM 또는 VIP")
        return

    sub.record_payment(target_id, tier, note=note)
    await update.effective_message.reply_text(
        f"💰 결제 확인: {target_id} → {tier}\n수익 DB에 기록됨"
    )


def run_bot() -> None:
    if not settings.telegram_token:
        print("TELEGRAM_TOKEN이 .env에 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    setup_logger("signal_lab_bot", settings.log_dir)
    logger.info("Starting Signal Lab Telegram bot")

    app = Application.builder().token(settings.telegram_token).build()

    handlers = [
        ("start", cmd_start),
        ("help", cmd_help),
        ("subscribe", cmd_subscribe),
        ("unsubscribe", cmd_unsubscribe),
        ("premium", cmd_premium),
        ("vip", cmd_vip),
        ("trial", cmd_trial),
        ("pay", cmd_pay),
        ("invite", cmd_invite),
        ("status", cmd_status),
        ("signals", cmd_signals),
        ("backtest", cmd_backtest),
        ("leaderboard", cmd_leaderboard),
        ("share", cmd_share),
        ("checkin", cmd_checkin),
        ("admin_stats", cmd_admin_stats),
        ("grant_premium", cmd_admin_grant),
        ("grant_vip", cmd_admin_grant_vip),
        ("confirm_payment", cmd_confirm_payment),
    ]
    for name, handler in handlers:
        app.add_handler(CommandHandler(name, handler))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
