from __future__ import annotations

import logging
import time

import requests

from config.settings import Settings
from database.db import SignalDatabase, SignalRecord
from subscription.manager import SubscriptionManager
from subscription.upsell import UpsellEngine

logger = logging.getLogger(__name__)


class TelegramSender:
    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        settings: Settings,
        db: SignalDatabase,
        subscription: SubscriptionManager | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.subscription = subscription or SubscriptionManager(settings, db)
        self.upsell = UpsellEngine(settings)

    def send_pending_signals(self) -> int:
        pending = self.db.get_unsent_signals()
        sent_count = 0
        premium_teasers: list[SignalRecord] = []

        for signal in pending:
            if signal.strategy in ("MACD", "CONFLUENCE"):
                premium_teasers.append(signal)

            recipients = self._resolve_recipients(signal)
            if not recipients:
                logger.warning("No recipients for signal %s %s", signal.ticker, signal.strategy)
                continue

            delivered = 0
            for chat_id in recipients:
                if not self.subscription.can_receive_signal(chat_id):
                    self._send_to_chat(chat_id, self.upsell.free_limit_message())
                    continue

                message = self._format_message(signal, chat_id)
                if self._send_to_chat(chat_id, message):
                    self.subscription.record_signal_sent(chat_id)
                    delivered += 1

            if delivered > 0:
                self.db.mark_signal_sent(signal.id)
                sent_count += 1

        if self.settings.upsell_enabled and premium_teasers:
            self._send_premium_teasers(premium_teasers)

        return sent_count

    def _send_premium_teasers(self, signals: list[SignalRecord]) -> None:
        free_users = self.db.get_free_subscribers()
        if not free_users:
            return

        seen: set[str] = set()
        for signal in signals:
            key = f"{signal.ticker}:{signal.strategy}"
            if key in seen:
                continue
            seen.add(key)

            teaser = self.upsell.teaser_for_signal(signal.ticker, signal.strategy, signal.signal_type)
            if not teaser:
                continue

            for sub in free_users:
                if self.subscription.is_premium(sub.chat_id):
                    continue
                self._send_to_chat(sub.chat_id, teaser)

    def send_upsell_broadcast(self) -> int:
        from datetime import datetime, timedelta

        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        count = self.db.count_premium_signals_since(week_start)
        message = self.upsell.weekly_upsell_message(count)

        sent = 0
        for sub in self.db.get_free_subscribers():
            if self._send_to_chat(sub.chat_id, message):
                sent += 1
        return sent

    def send_to_subscribers(self, message: str, tier: str | None = None) -> int:
        subscribers = self.db.get_active_subscribers()
        sent = 0
        for sub in subscribers:
            if tier and self.subscription.effective_tier(sub.chat_id) != tier:
                if tier == self.settings.premium_tier_name and not self.subscription.is_premium(sub.chat_id):
                    continue
                elif tier == self.settings.vip_tier_name and not self.subscription.is_vip(sub.chat_id):
                    continue
            if self._send_to_chat(sub.chat_id, message):
                sent += 1

        if sent == 0 and self.settings.telegram_chat_id.isdigit():
            if self._send_to_chat(int(self.settings.telegram_chat_id), message):
                return 1
        return sent

    def send_to_admin(self, message: str) -> int:
        sent = 0
        for chat_id in self.settings.admin_chat_ids:
            if self._send_to_chat(chat_id, message):
                sent += 1
        return sent

    def _resolve_recipients(self, signal: SignalRecord) -> list[int]:
        subscribers = self.db.get_active_subscribers()
        recipients: list[int] = []

        for sub in subscribers:
            if signal.ticker not in self.subscription.allowed_tickers(sub.chat_id):
                continue
            if not self.subscription.can_receive_strategy(sub.chat_id, signal.strategy):
                continue
            recipients.append(sub.chat_id)

        if not recipients:
            for chat_id in self.settings.admin_chat_ids:
                recipients.append(chat_id)
            if not recipients and self.settings.telegram_chat_id.isdigit():
                recipients.append(int(self.settings.telegram_chat_id))

        return list(dict.fromkeys(recipients))

    def _send_to_chat(self, chat_id: int, message: str) -> bool:
        if not self.settings.telegram_token:
            return False

        url = self.API_URL.format(token=self.settings.telegram_token)
        for attempt in range(1, self.settings.api_retry_count + 1):
            try:
                response = requests.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    return True
                logger.error(
                    "Telegram send failed (attempt %d/%d) chat=%s status=%s",
                    attempt,
                    self.settings.api_retry_count,
                    chat_id,
                    response.status_code,
                )
            except requests.RequestException:
                logger.exception(
                    "Telegram request error (attempt %d/%d) chat=%s",
                    attempt,
                    self.settings.api_retry_count,
                    chat_id,
                )
            if attempt < self.settings.api_retry_count:
                time.sleep(self.settings.api_retry_delay)
        return False

    def _format_message(self, signal: SignalRecord, chat_id: int) -> str:
        if signal.strategy == "MACD":
            base = self._format_macd_message(signal)
        elif signal.strategy == "CONFLUENCE":
            base = self._format_confluence_message(signal)
        else:
            base = self._format_rsi_message(signal)

        if not self.subscription.is_premium(chat_id) and signal.strategy == "RSI":
            return UpsellEngine.append_upsell_footer(base, self.settings)
        return base

    @staticmethod
    def _format_rsi_message(signal: SignalRecord) -> str:
        if signal.signal_type == "BUY":
            emoji, label = "🟢", "매수 시그널 (RSI)"
        else:
            emoji, label = "🔴", "매도 시그널 (RSI)"

        return (
            f"<b>Signal Lab</b>\n\n"
            f"{emoji} <b>{signal.ticker}</b> — {label}\n"
            f"RSI: <code>{signal.rsi}</code>\n"
            f"Price: <code>${signal.price}</code>\n"
            f"Date: <code>{signal.signal_date}</code>"
        )

    @staticmethod
    def _format_macd_message(signal: SignalRecord) -> str:
        if signal.signal_type == "BUY":
            emoji, label = "🟢", "매수 시그널 (MACD Golden Cross)"
        else:
            emoji, label = "🔴", "매도 시그널 (MACD Dead Cross)"

        return (
            f"<b>Signal Lab PREMIUM</b>\n\n"
            f"{emoji} <b>{signal.ticker}</b> — {label}\n"
            f"MACD: <code>{signal.macd_line}</code>\n"
            f"Signal: <code>{signal.macd_signal_line}</code>\n"
            f"Price: <code>${signal.price}</code>\n"
            f"Date: <code>{signal.signal_date}</code>"
        )

    @staticmethod
    def _format_confluence_message(signal: SignalRecord) -> str:
        if signal.signal_type == "BUY":
            emoji, label = "💎", "강력 매수 (RSI+MACD Confluence)"
        else:
            emoji, label = "💎", "강력 매도 (RSI+MACD Confluence)"

        return (
            f"<b>Signal Lab VIP ⭐</b>\n\n"
            f"{emoji} <b>{signal.ticker}</b> — {label}\n"
            f"RSI: <code>{signal.rsi}</code>\n"
            f"MACD: <code>{signal.macd_line}</code> / <code>{signal.macd_signal_line}</code>\n"
            f"Price: <code>${signal.price}</code>\n"
            f"Date: <code>{signal.signal_date}</code>\n"
            f"신뢰도: {'★' * signal.strength}"
        )
