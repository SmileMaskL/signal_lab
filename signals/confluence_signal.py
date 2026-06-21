from __future__ import annotations

import logging

from config.settings import Settings
from database.db import SignalDatabase, SignalRecord
from utils.macd import calculate_macd, detect_macd_cross
from utils.rsi import latest_rsi

logger = logging.getLogger(__name__)


class ConfluenceSignalGenerator:
    """Premium signal: RSI + MACD agreement on the same day (high confidence)."""

    BUY = "BUY"
    SELL = "SELL"
    STRATEGY = "CONFLUENCE"

    def __init__(self, settings: Settings, db: SignalDatabase) -> None:
        self.settings = settings
        self.db = db

    def generate_all(self) -> list[SignalRecord]:
        signals: list[SignalRecord] = []
        for ticker in self.settings.tickers:
            signal = self.generate_for_ticker(ticker)
            if signal:
                signals.append(signal)
        return signals

    def generate_for_ticker(self, ticker: str) -> SignalRecord | None:
        prices = self.db.get_prices(ticker)
        min_rows = max(
            self.settings.rsi_period + 1,
            self.settings.macd_slow_period + self.settings.macd_signal_period,
        )
        if len(prices) < min_rows:
            logger.warning("Not enough data for confluence %s", ticker)
            return None

        closes = [p.close for p in prices]
        rsi_value = latest_rsi(closes, self.settings.rsi_period)
        macd_line, signal_line = calculate_macd(
            closes,
            self.settings.macd_fast_period,
            self.settings.macd_slow_period,
            self.settings.macd_signal_period,
        )
        cross_type = detect_macd_cross(macd_line, signal_line)

        if rsi_value is None or cross_type is None:
            return None

        signal_type: str | None = None
        if cross_type == self.BUY and rsi_value <= self.settings.rsi_buy_threshold:
            signal_type = self.BUY
        elif cross_type == self.SELL and rsi_value >= self.settings.rsi_sell_threshold:
            signal_type = self.SELL

        if signal_type is None:
            logger.info(
                "%s confluence: RSI=%.2f, MACD=%s -> no agreement",
                ticker,
                rsi_value,
                cross_type,
            )
            return None

        latest = prices[-1]
        signal = SignalRecord(
            ticker=ticker,
            signal_type=signal_type,
            strategy=self.STRATEGY,
            rsi=round(rsi_value, 2),
            macd_line=round(macd_line[-1], 4) if macd_line[-1] is not None else None,
            macd_signal_line=round(signal_line[-1], 4) if signal_line[-1] is not None else None,
            price=round(latest.close, 2),
            signal_date=latest.date,
            created_at=SignalDatabase.now_iso(),
            sent=0,
            strength=3,
        )

        signal_id = self.db.insert_signal(signal)
        if signal_id is None:
            logger.info("%s confluence %s already exists for %s", ticker, signal_type, latest.date)
            return None

        signal.id = signal_id
        logger.info(
            "%s CONFLUENCE %s | RSI=%.2f | Price=%.2f",
            ticker,
            signal_type,
            rsi_value,
            latest.close,
        )
        return signal
