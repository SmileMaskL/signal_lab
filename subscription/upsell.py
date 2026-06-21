from __future__ import annotations

import logging
from datetime import datetime, timedelta

from config.settings import Settings

logger = logging.getLogger(__name__)

TIER_RANK = {"FREE": 0, "PREMIUM": 1, "VIP": 2}


class UpsellEngine:
    """Send conversion messages to free users when premium signals occur."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def teaser_for_signal(self, ticker: str, strategy: str, signal_type: str) -> str:
        action = "매수" if signal_type == "BUY" else "매도"
        if strategy == "CONFLUENCE":
            headline = f"💎 <b>{ticker}</b> 강력 {action} 시그널 발생!"
            detail = "RSI+MACD 동시 일치 — VIP 전용"
        elif strategy == "MACD":
            headline = f"⚡ <b>{ticker}</b> MACD {action} 시그널 발생!"
            detail = "프리미엄 이상만 즉시 수신"
        else:
            return ""

        return (
            f"🔒 <b>[프리미엄 미리보기]</b>\n\n"
            f"{headline}\n"
            f"{detail}\n\n"
            f"지금 업그레이드:\n"
            f"• PREMIUM ₩{self.settings.premium_price_krw:,}/월\n"
            f"• VIP ₩{self.settings.vip_price_krw:,}/월 (최고급)\n\n"
            f"/pay — 결제 방법\n"
            f"/trial — {self.settings.trial_days}일 무료 체험"
        )

    def weekly_upsell_message(self, premium_signal_count: int) -> str:
        return (
            "📢 <b>이번 주 프리미엄 시그널 요약</b>\n\n"
            f"프리미엄/VIP 전용 시그널 <b>{premium_signal_count}건</b> 발생\n"
            f"무료 회원은 RSI {self.settings.free_weekly_signal_limit}건만 수신 가능\n\n"
            f"💎 PREMIUM ₩{self.settings.premium_price_krw:,}/월\n"
            f"   → MACD + 전체 종목 + 일일 리포트\n\n"
            f"👑 VIP ₩{self.settings.vip_price_krw:,}/월\n"
            f"   → Confluence + 최우선 알림\n\n"
            f"/pay 결제 | /trial {self.settings.trial_days}일 체험"
        )

    def free_limit_message(self) -> str:
        return (
            f"⚠️ 이번 주 무료 시그널 한도({self.settings.free_weekly_signal_limit}건)를 모두 사용했습니다.\n\n"
            f"/premium — 프리미엄 업그레이드\n"
            f"/trial — {self.settings.trial_days}일 무료 체험"
        )

    @staticmethod
    def append_upsell_footer(message: str, settings: Settings) -> str:
        return (
            f"{message}\n\n"
            f"──────────\n"
            f"💡 MACD/Confluence 시그널은 PREMIUM 이상 → /premium"
        )
