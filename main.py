from __future__ import annotations

import argparse
import logging
import time

import requests
import schedule

from backtest.backtester import Backtester
from config.settings import settings
from data.collector import StockCollector
from database.db import SignalDatabase
from reports.daily_report import DailyReportGenerator
from signals.bollinger_bands import BollingerBandsSignalGenerator
from signals.confluence_signal import ConfluenceSignalGenerator
from signals.macd_signal import MACDSignalGenerator
from signals.rsi_signal import RSISignalGenerator
from subscription.manager import SubscriptionManager
from telegram_bot.sender import TelegramSender
from utils.logger import setup_logger

logger = logging.getLogger(__name__)


def send_telegram_fallback(text: str) -> None:
    """Send system alerts to admin without exposing token in logs."""
    token = settings.telegram_token
    if not token:
        logger.warning("Telegram token missing; cannot send system message")
        return

    recipients = list(settings.admin_chat_ids)
    if not recipients and settings.telegram_chat_id.isdigit():
        recipients.append(int(settings.telegram_chat_id))

    if not recipients:
        logger.warning("No admin chat IDs configured")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in recipients:
        try:
            response = requests.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("System message sent to admin chat %s", chat_id)
            else:
                logger.error(
                    "System message failed for chat %s (HTTP %s)",
                    chat_id,
                    response.status_code,
                )
        except Exception as exc:
            logger.error("System message error for chat %s: %s", chat_id, exc)


def run_pipeline() -> None:
    logger.info("=== Signal Lab pipeline started ===")

    try:
        db = SignalDatabase(settings.db_path)
        subscription = SubscriptionManager(settings, db)
        collector = StockCollector(settings, db)
        rsi_gen = RSISignalGenerator(settings, db)
        macd_gen = MACDSignalGenerator(settings, db)
        confluence_gen = ConfluenceSignalGenerator(settings, db)
        bb_gen = BollingerBandsSignalGenerator(settings, db)
        telegram = TelegramSender(settings, db, subscription)
        report_gen = DailyReportGenerator(settings, db)

        saved_rows = collector.collect_all()
        logger.info("Total price rows saved: %d", saved_rows)

        rsi_signals = rsi_gen.generate_all()
        logger.info("New RSI signals generated: %d", len(rsi_signals))

        macd_signals = macd_gen.generate_all()
        logger.info("New MACD signals generated: %d", len(macd_signals))

        confluence_signals = confluence_gen.generate_all()
        logger.info("New Confluence signals generated: %d", len(confluence_signals))

        bb_signals = bb_gen.generate_all()
        logger.info("New Bollinger Bands signals generated: %d", len(bb_signals))

        total_signals = len(rsi_signals) + len(macd_signals) + len(confluence_signals) + len(bb_signals)
        logger.info("New signals generated: %d", total_signals)

        sent_count = telegram.send_pending_signals()
        logger.info("Telegram signal messages delivered: %d", sent_count)

        if settings.daily_report_enabled:
            report = report_gen.generate()
            premium_sent = 0
            for sub in db.get_active_subscribers():
                if subscription.is_premium(sub.chat_id):
                    if telegram._send_to_chat(sub.chat_id, report):
                        premium_sent += 1
            logger.info("Daily report sent to %d premium/vip subscribers", premium_sent)

        if sent_count == 0 and settings.heartbeat_enabled:
            stats = db.revenue_stats()
            heartbeat_msg = (
                "✅ <b>[Signal Lab] 일일 파이프라인 완료</b>\n\n"
                f"가격 데이터: {saved_rows}건 | 신규 시그널: {total_signals}건\n"
                f"구독: FREE {stats['free_count']} | PREMIUM {stats['premium_count']} | VIP {stats['vip_count']}\n"
                f"예상 MRR: ₩{stats['estimated_mrr_krw']:,}\n\n"
                "오늘 새 시그널 없음."
            )
            send_telegram_fallback(heartbeat_msg)

    except Exception as exc:
        error_msg = (
            "⚠️ <b>[Signal Lab] 시스템 오류</b>\n\n"
            f"파이프라인 실행 중 예외가 발생했습니다.\n"
            f"에러: <code>{type(exc).__name__}: {exc}</code>"
        )
        logger.error("Pipeline error: %s", exc, exc_info=True)
        send_telegram_fallback(error_msg)

    logger.info("=== Signal Lab pipeline finished ===")


def run_backtest() -> None:
    setup_logger("signal_lab", settings.log_dir)
    db = SignalDatabase(settings.db_path)
    collector = StockCollector(settings, db)
    collector.collect_all()

    backtester = Backtester(settings, db)
    results = backtester.run_all()
    logger.info("Backtest completed: %d result sets", len(results))


def run_upsell_broadcast() -> None:
    logger.info("=== Upsell broadcast started ===")
    try:
        db = SignalDatabase(settings.db_path)
        subscription = SubscriptionManager(settings, db)
        telegram = TelegramSender(settings, db, subscription)
        sent = telegram.send_upsell_broadcast()
        logger.info("Upsell messages sent: %d", sent)
    except Exception as exc:
        logger.error("Upsell broadcast error: %s", exc)


def start_scheduler() -> None:
    startup_msg = (
        "🚀 <b>[Signal Lab] 구동 시작</b>\n\n"
        f"매일 <b>{settings.schedule_time}</b> 시그널 분석\n"
        f"매일 <b>{settings.upsell_time}</b> 무료→유료 업셀\n"
        f"등급: FREE / PREMIUM / VIP"
    )
    send_telegram_fallback(startup_msg)

    schedule.every().day.at(settings.schedule_time).do(run_pipeline)
    if settings.upsell_enabled:
        schedule.every().day.at(settings.upsell_time).do(run_upsell_broadcast)
    logger.info(
        "Scheduler started | signals at %s | upsell at %s",
        settings.schedule_time,
        settings.upsell_time,
    )

    run_pipeline()

    while True:
        try:
            schedule.run_pending()
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc)
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Signal Lab - US Stock Signal Bot")
    parser.add_argument("--once", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--backtest", action="store_true", help="Run backtest and save results")
    parser.add_argument("--bot", action="store_true", help="Run interactive Telegram bot")
    args = parser.parse_args()

    if args.bot:
        from telegram_bot.bot import run_bot

        run_bot()
        return

    setup_logger("signal_lab", settings.log_dir)

    if args.backtest:
        run_backtest()
    elif args.once:
        run_pipeline()
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
