from __future__ import annotations

import logging

from config.settings import Settings
from database.db import SignalDatabase
from utils.macd import calculate_macd
from utils.rsi import latest_rsi

logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """Generate daily market summary for premium subscribers."""

    def __init__(self, settings: Settings, db: SignalDatabase) -> None:
        self.settings = settings
        self.db = db

    def generate(self, tickers: tuple[str, ...] | None = None) -> str:
        watchlist = tickers or self.settings.tickers
        lines = [
            "📋 <b>[Signal Lab] 일일 시장 리포트</b>\n",
            f"분석 종목: {', '.join(watchlist)}\n",
        ]

        buy_count = 0
        sell_count = 0

        for ticker in watchlist:
            prices = self.db.get_prices(ticker)
            if len(prices) < self.settings.rsi_period + 1:
                lines.append(f"⚪ <b>{ticker}</b>: 데이터 부족")
                continue

            closes = [p.close for p in prices]
            rsi = latest_rsi(closes, self.settings.rsi_period)
            macd_line, signal_line = calculate_macd(
                closes,
                self.settings.macd_fast_period,
                self.settings.macd_slow_period,
                self.settings.macd_signal_period,
            )

            latest = prices[-1]
            rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
            macd_val = macd_line[-1]
            sig_val = signal_line[-1]
            macd_str = f"{macd_val:.4f}" if macd_val is not None else "N/A"
            sig_str = f"{sig_val:.4f}" if sig_val is not None else "N/A"

            trend = self._trend_label(rsi, macd_val, sig_val)
            if trend == "BUY":
                buy_count += 1
            elif trend == "SELL":
                sell_count += 1

            lines.append(
                f"{self._trend_emoji(trend)} <b>{ticker}</b> ${latest.close:.2f}\n"
                f"   RSI {rsi_str} | MACD {macd_str} / {sig_str} | {trend}"
            )

        recent = self.db.get_recent_signals(limit=5)
        if recent:
            lines.append("\n🔔 <b>최근 시그널</b>")
            for sig in recent:
                lines.append(
                    f"  • {sig.signal_date} {sig.ticker} {sig.signal_type} [{sig.strategy}]"
                )

        lines.append(
            f"\n📈 매수 관심 {buy_count}종목 | 📉 매도 관심 {sell_count}종목"
        )
        lines.append("\n<i>투자 판단은 본인 책임입니다. Signal Lab은 정보 제공 서비스입니다.</i>")

        return "\n".join(lines)

    @staticmethod
    def _trend_label(
        rsi: float | None,
        macd: float | None,
        signal: float | None,
    ) -> str:
        if rsi is not None and rsi <= 30:
            return "BUY"
        if rsi is not None and rsi >= 70:
            return "SELL"
        if macd is not None and signal is not None:
            if macd > signal:
                return "BULLISH"
            if macd < signal:
                return "BEARISH"
        return "NEUTRAL"

    @staticmethod
    def _trend_emoji(trend: str) -> str:
        return {
            "BUY": "🟢",
            "SELL": "🔴",
            "BULLISH": "🔵",
            "BEARISH": "🟠",
            "NEUTRAL": "⚪",
        }.get(trend, "⚪")
