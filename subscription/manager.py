from __future__ import annotations

from datetime import datetime, timedelta

from config.settings import Settings
from database.db import SignalDatabase, SubscriberRecord

TIER_RANK = {"FREE": 0, "PREMIUM": 1, "VIP": 2}


class SubscriptionManager:
    """Manage FREE / PREMIUM / VIP tiers, trials, referrals, and payments."""

    def __init__(self, settings: Settings, db: SignalDatabase) -> None:
        self.settings = settings
        self.db = db

    def subscribe_free(
        self,
        chat_id: int,
        username: str | None = None,
        referred_by: int | None = None,
    ) -> SubscriberRecord:
        return self.db.upsert_subscriber(
            chat_id=chat_id,
            tier=self.settings.free_tier_name,
            username=username,
            referred_by=referred_by,
        )

    def subscribe_premium(
        self,
        chat_id: int,
        username: str | None = None,
        days: int | None = None,
    ) -> SubscriberRecord:
        expires = self._expiry(days or self.settings.premium_duration_days)
        return self.db.upsert_subscriber(
            chat_id=chat_id,
            tier=self.settings.premium_tier_name,
            username=username,
            premium_expires_at=expires,
        )

    def subscribe_vip(
        self,
        chat_id: int,
        username: str | None = None,
        days: int | None = None,
    ) -> SubscriberRecord:
        expires = self._expiry(days or self.settings.vip_duration_days)
        return self.db.upsert_subscriber(
            chat_id=chat_id,
            tier=self.settings.vip_tier_name,
            username=username,
            premium_expires_at=expires,
        )

    def start_trial(self, chat_id: int, username: str | None = None) -> SubscriberRecord | None:
        sub = self.db.get_subscriber(chat_id)
        if sub and sub.trial_expires_at:
            return None

        trial_end = self._expiry(self.settings.trial_days)
        return self.db.upsert_subscriber(
            chat_id=chat_id,
            tier=self.settings.premium_tier_name,
            username=username,
            trial_expires_at=trial_end,
        )

    def unsubscribe(self, chat_id: int) -> bool:
        return self.db.deactivate_subscriber(chat_id)

    def get_subscriber(self, chat_id: int) -> SubscriberRecord | None:
        return self.db.get_subscriber(chat_id)

    def effective_tier(self, chat_id: int) -> str:
        sub = self.db.get_subscriber(chat_id)
        if sub is None or sub.active != 1:
            return self.settings.free_tier_name
        if self.is_admin(chat_id):
            return self.settings.vip_tier_name

        now = datetime.now()
        if sub.trial_expires_at and datetime.fromisoformat(sub.trial_expires_at) > now:
            return self.settings.premium_tier_name
        if sub.premium_expires_at and datetime.fromisoformat(sub.premium_expires_at) > now:
            return sub.tier
        if sub.tier in (self.settings.premium_tier_name, self.settings.vip_tier_name):
            if not sub.premium_expires_at:
                return sub.tier
        return self.settings.free_tier_name

    def is_premium(self, chat_id: int) -> bool:
        tier = self.effective_tier(chat_id)
        return TIER_RANK.get(tier, 0) >= TIER_RANK[self.settings.premium_tier_name]

    def is_vip(self, chat_id: int) -> bool:
        return self.effective_tier(chat_id) == self.settings.vip_tier_name

    def is_admin(self, chat_id: int) -> bool:
        return chat_id in self.settings.admin_chat_ids

    def validate_premium_code(self, code: str) -> bool:
        return code.strip() in self.settings.premium_codes

    def validate_vip_code(self, code: str) -> bool:
        return code.strip() in self.settings.vip_codes

    def allowed_tickers(self, chat_id: int) -> tuple[str, ...]:
        tier = self.effective_tier(chat_id)
        if tier == self.settings.vip_tier_name or self.is_admin(chat_id):
            return self.settings.vip_tickers
        if tier == self.settings.premium_tier_name:
            return self.settings.tickers
        return self.settings.free_tickers

    def can_receive_strategy(self, chat_id: int, strategy: str) -> bool:
        tier = self.effective_tier(chat_id)
        if self.is_admin(chat_id):
            return True
        if strategy == "RSI":
            return True
        if strategy == "MACD":
            return TIER_RANK.get(tier, 0) >= TIER_RANK[self.settings.premium_tier_name]
        if strategy == "CONFLUENCE":
            return tier == self.settings.vip_tier_name
        return False

    def can_receive_signal(self, chat_id: int) -> bool:
        tier = self.effective_tier(chat_id)
        if tier != self.settings.free_tier_name:
            return True
        count = self.db.get_weekly_signal_count(chat_id)
        return count < self.settings.free_weekly_signal_limit

    def record_signal_sent(self, chat_id: int) -> None:
        if self.effective_tier(chat_id) == self.settings.free_tier_name:
            self.db.increment_weekly_signal(chat_id)

    def apply_referral(self, referrer_code: str, new_chat_id: int) -> SubscriberRecord | None:
        referrer = self.db.get_subscriber_by_referral_code(referrer_code.upper())
        if referrer is None or referrer.chat_id == new_chat_id:
            return None

        if not self.db.record_referral(referrer.chat_id, new_chat_id):
            return None

        # Multi-tier referral bonus system
        referral_count = self.db.referral_count(referrer.chat_id)
        
        # Tiered bonus: more referrals = more bonus days
        if referral_count >= 10:
            bonus_days = self.settings.referral_bonus_days * 2  # 2x bonus for 10+ referrals
        elif referral_count >= 5:
            bonus_days = int(self.settings.referral_bonus_days * 1.5)  # 1.5x bonus for 5+ referrals
        else:
            bonus_days = self.settings.referral_bonus_days

        current = self.db.get_subscriber(referrer.chat_id)
        base = datetime.now()
        if current and current.premium_expires_at:
            try:
                existing = datetime.fromisoformat(current.premium_expires_at)
                if existing > base:
                    base = existing
            except ValueError:
                pass

        new_expiry = (base + timedelta(days=bonus_days)).isoformat(timespec="seconds")
        tier = current.tier if current and current.tier != self.settings.free_tier_name else self.settings.premium_tier_name
        return self.db.upsert_subscriber(
            chat_id=referrer.chat_id,
            tier=tier,
            premium_expires_at=new_expiry,
        )

    def referral_link(self, chat_id: int) -> str:
        sub = self.db.get_subscriber(chat_id)
        code = sub.referral_code if sub else f"SL{chat_id}"
        bot = self.settings.bot_username.lstrip("@")
        return f"https://t.me/{bot}?start={code}"

    def record_payment(self, chat_id: int, tier: str, note: str = "") -> SubscriberRecord:
        if tier == self.settings.vip_tier_name:
            amount = self.settings.vip_price_krw
            sub = self.subscribe_vip(chat_id)
        else:
            amount = self.settings.premium_price_krw
            sub = self.subscribe_premium(chat_id)

        self.db.record_payment(chat_id, tier, amount, note=note)
        return sub

    def pricing_message(self) -> str:
        return (
            f"💎 <b>Signal Lab 요금제</b>\n\n"
            f"🆓 <b>FREE</b> — ₩0\n"
            f"  • {', '.join(self.settings.free_tickers)} ({len(self.settings.free_tickers)}종목)\n"
            f"  • RSI 시그널 (주 {self.settings.free_weekly_signal_limit}건)\n\n"
            f"⭐ <b>PREMIUM</b> — ₩{self.settings.premium_price_krw:,}/월\n"
            f"  • 전체 {len(self.settings.tickers)}종목\n"
            f"  • RSI + MACD 시그널\n"
            f"  • 일일 시장 리포트 + 백테스트\n\n"
            f"👑 <b>VIP</b> — ₩{self.settings.vip_price_krw:,}/월\n"
            f"  • PREMIUM 전체 + Confluence 강력 시그널\n"
            f"  • 최우선 알림 + {len(self.settings.vip_tickers)}종목\n\n"
            f"🎁 <b>{self.settings.trial_days}일 무료 체험</b> → /trial\n"
            f"💳 결제 → /pay\n"
            f"🔗 친구 추천 → /invite (추천 시 {self.settings.referral_bonus_days}일 추가)"
        )

    def pay_message(self) -> str:
        lines = [
            "💳 <b>결제 방법</b>\n",
            f"⭐ PREMIUM: ₩{self.settings.premium_price_krw:,}/월 (${self.settings.premium_price_usd})",
            f"👑 VIP: ₩{self.settings.vip_price_krw:,}/월 (${self.settings.vip_price_usd})\n",
        ]
        if self.settings.payment_link_krw:
            lines.append(f"🇰🇷 <a href=\"{self.settings.payment_link_krw}\">원화 결제 링크</a>")
        if self.settings.payment_link_usd:
            lines.append(f"🇺🇸 <a href=\"{self.settings.payment_link_usd}\">달러 결제 링크</a>")
        lines.append(
            f"\n결제 후 {self.settings.payment_contact} 로 스크린샷 전송\n"
            f"또는 코드 입력:\n"
            f"  /premium 코드 — PREMIUM\n"
            f"  /vip 코드 — VIP"
        )
        return "\n".join(lines)

    @staticmethod
    def _expiry(days: int) -> str:
        return (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds")
