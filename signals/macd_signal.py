from __future__ import annotations

import logging

from config.settings import Settings
from database.db import SignalDatabase, SignalRecord
from utils.macd import calculate_macd, detect_macd_cross

logger = logging.getLogger(__name__)


class MACDSignalGenerator:
    BUY = "BUY"
    SELL = "SELL"
    STRATEGY = "MACD"

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
        min_rows = self.settings.macd_slow_period + self.settings.macd_signal_period
        if len(prices) < min_rows:
            logger.warning(
                "Not enough data for MACD %s (need %d, got %d)",
                ticker,
                min_rows,
                len(prices),
            )
            return None

        closes = [p.close for p in prices]
        macd_line, signal_line = calculate_macd(
            closes,
            fast_period=self.settings.macd_fast_period,
            slow_period=self.settings.macd_slow_period,
            signal_period=self.settings.macd_signal_period,
        )

        cross_type = detect_macd_cross(macd_line, signal_line)
        latest_macd = macd_line[-1]
        latest_signal = signal_line[-1]

        if cross_type is None:
            if latest_macd is not None and latest_signal is not None:
                logger.info(
                    "%s MACD=%.4f Signal=%.4f -> no cross",
                    ticker,
                    latest_macd,
                    latest_signal,
                )
            else:
                logger.warning("MACD calculation failed for %s", ticker)
            return None

        latest = prices[-1]
        signal = SignalRecord(
            ticker=ticker,
            signal_type=cross_type,
            strategy=self.STRATEGY,
            rsi=0.0,
            macd_line=round(latest_macd, 4) if latest_macd is not None else None,
            macd_signal_line=round(latest_signal, 4) if latest_signal is not None else None,
            price=round(latest.close, 2),
            signal_date=latest.date,
            created_at=SignalDatabase.now_iso(),
            sent=0,
        )

        signal_id = self.db.insert_signal(signal)
        if signal_id is None:
            logger.info(
                "%s MACD %s signal already exists for %s",
                ticker,
                cross_type,
                latest.date,
            )
            return None

        signal.id = signal_id
        cross_label = "Golden Cross" if cross_type == self.BUY else "Dead Cross"
        logger.info(
            "%s MACD %s (%s) generated | MACD=%.4f | Signal=%.4f | Price=%.2f",
            ticker,
            cross_type,
            cross_label,
            latest_macd,
            latest_signal,
            latest.close,
        )
        return signal
