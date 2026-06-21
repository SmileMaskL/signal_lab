from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value or not value.strip():
        return default
    return tuple(item.strip().upper() for item in value.split(",") if item.strip())


def _parse_int_csv(value: str | None) -> tuple[int, ...]:
    if not value or not value.strip():
        return ()
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    project_name: str = "Signal Lab"
    base_dir: Path = BASE_DIR
    db_path: Path = field(default_factory=lambda: BASE_DIR / "signal.db")
    log_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")

    tickers: tuple[str, ...] = field(
        default_factory=lambda: _parse_csv(
            os.getenv("TICKERS"),
            ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN"),
        )
    )
    free_tickers: tuple[str, ...] = field(
        default_factory=lambda: _parse_csv(
            os.getenv("FREE_TICKERS"),
            ("SPY", "QQQ"),
        )
    )
    vip_tickers: tuple[str, ...] = field(
        default_factory=lambda: _parse_csv(
            os.getenv("VIP_TICKERS"),
            ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN"),
        )
    )

    rsi_period: int = int(os.getenv("RSI_PERIOD", "14"))
    rsi_buy_threshold: float = float(os.getenv("RSI_BUY_THRESHOLD", "30"))
    rsi_sell_threshold: float = float(os.getenv("RSI_SELL_THRESHOLD", "70"))

    macd_fast_period: int = int(os.getenv("MACD_FAST", "12"))
    macd_slow_period: int = int(os.getenv("MACD_SLOW", "26"))
    macd_signal_period: int = int(os.getenv("MACD_SIGNAL", "9"))

    history_days: int = int(os.getenv("HISTORY_DAYS", "120"))
    backtest_days: int = int(os.getenv("BACKTEST_DAYS", "365"))
    backtest_hold_days: int = int(os.getenv("BACKTEST_HOLD_DAYS", "10"))

    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    bot_username: str = field(default_factory=lambda: os.getenv("BOT_USERNAME", "YourSignalLabBot"))
    admin_chat_ids: tuple[int, ...] = field(
        default_factory=lambda: _parse_int_csv(os.getenv("ADMIN_CHAT_IDS"))
        or (
            (int(os.getenv("TELEGRAM_CHAT_ID")),)
            if os.getenv("TELEGRAM_CHAT_ID", "").isdigit()
            else ()
        )
    )
    premium_codes: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            code.strip()
            for code in os.getenv("PREMIUM_CODES", "SIGNAL2026,PREMIUM").split(",")
            if code.strip()
        )
    )
    vip_codes: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            code.strip()
            for code in os.getenv("VIP_CODES", "VIP2026,SIGNALVIP").split(",")
            if code.strip()
        )
    )

    schedule_time: str = os.getenv("SCHEDULE_TIME", "22:00")
    upsell_time: str = os.getenv("UPSELL_TIME", "12:00")
    heartbeat_enabled: bool = os.getenv("HEARTBEAT_ENABLED", "true").lower() == "true"
    daily_report_enabled: bool = os.getenv("DAILY_REPORT_ENABLED", "true").lower() == "true"
    upsell_enabled: bool = os.getenv("UPSELL_ENABLED", "true").lower() == "true"

    api_retry_count: int = int(os.getenv("API_RETRY_COUNT", "3"))
    api_retry_delay: float = float(os.getenv("API_RETRY_DELAY", "2.0"))

    free_tier_name: str = "FREE"
    premium_tier_name: str = "PREMIUM"
    vip_tier_name: str = "VIP"

    premium_price_krw: int = int(os.getenv("PREMIUM_PRICE_KRW", "29000"))
    premium_price_usd: float = float(os.getenv("PREMIUM_PRICE_USD", "19.99"))
    vip_price_krw: int = int(os.getenv("VIP_PRICE_KRW", "59000"))
    vip_price_usd: float = float(os.getenv("VIP_PRICE_USD", "39.99"))

    payment_link_krw: str = field(default_factory=lambda: os.getenv("PAYMENT_LINK_KRW", ""))
    payment_link_usd: str = field(default_factory=lambda: os.getenv("PAYMENT_LINK_USD", ""))
    payment_contact: str = field(
        default_factory=lambda: os.getenv("PAYMENT_CONTACT", "@YourTelegramID")
    )

    # Korean bank transfer info
    bank_name: str = field(default_factory=lambda: os.getenv("BANK_NAME", ""))
    bank_account: str = field(default_factory=lambda: os.getenv("BANK_ACCOUNT", ""))
    bank_holder: str = field(default_factory=lambda: os.getenv("BANK_HOLDER", ""))

    # Web settings
    web_domain: str = field(default_factory=lambda: os.getenv("WEB_DOMAIN", "localhost"))
    web_protocol: str = field(default_factory=lambda: os.getenv("WEB_PROTOCOL", "http"))

    trial_days: int = int(os.getenv("TRIAL_DAYS", "3"))
    referral_bonus_days: int = int(os.getenv("REFERRAL_BONUS_DAYS", "7"))
    free_weekly_signal_limit: int = int(os.getenv("FREE_WEEKLY_SIGNAL_LIMIT", "2"))
    premium_duration_days: int = int(os.getenv("PREMIUM_DURATION_DAYS", "30"))
    vip_duration_days: int = int(os.getenv("VIP_DURATION_DAYS", "30"))


settings = Settings()
