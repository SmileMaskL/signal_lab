from __future__ import annotations

import logging

from config.settings import Settings
from database.db import SignalDatabase, SignalRecord
from utils.rsi import latest_rsi

logger = logging.getLogger(__name__)


class RSISignalGenerator:
    BUY = "BUY"
    SELL = "SELL"
    STRATEGY = "RSI"

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
        min_rows = self.settings.rsi_period + 1
        if len(prices) < min_rows:
            logger.warning(
                "Not enough data for %s (need %d, got %d)",
                ticker,
                min_rows,
                len(prices),
            )
            return None

        closes = [p.close for p in prices]
        rsi_value = latest_rsi(closes, self.settings.rsi_period)
        if rsi_value is None:
            logger.warning("RSI calculation failed for %s", ticker)
            return None

        latest = prices[-1]
        signal_type = self._resolve_signal_type(rsi_value)
        if signal_type is None:
            logger.info("%s RSI=%.2f -> no signal", ticker, rsi_value)
            return None

        signal = SignalRecord(
            ticker=ticker,
            signal_type=signal_type,
            strategy=self.STRATEGY,
            rsi=round(rsi_value, 2),
            price=round(latest.close, 2),
            signal_date=latest.date,
            created_at=SignalDatabase.now_iso(),
            sent=0,
        )

        signal_id = self.db.insert_signal(signal)
        if signal_id is None:
            logger.info(
                "%s RSI %s signal already exists for %s",
                ticker,
                signal_type,
                latest.date,
            )
            return None

        signal.id = signal_id
        logger.info(
            "%s RSI %s signal generated | RSI=%.2f | Price=%.2f",
            ticker,
            signal_type,
            rsi_value,
            latest.close,
        )
        return signal

    def _resolve_signal_type(self, rsi_value: float) -> str | None:
        if rsi_value <= self.settings.rsi_buy_threshold:
            return self.BUY
        if rsi_value >= self.settings.rsi_sell_threshold:
            return self.SELL
        return None
