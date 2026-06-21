"""Bollinger Bands signal generator for enhanced trading signals."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from config.settings import Settings
from database.db import SignalDatabase, SignalRecord

logger = logging.getLogger(__name__)


@dataclass
class BollingerBandsResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    percent_b: float


class BollingerBandsSignalGenerator:
    """Generate Bollinger Bands-based trading signals."""

    def __init__(self, settings: Settings, db: SignalDatabase) -> None:
        self.settings = settings
        self.db = db
        self.period = 20
        self.std_dev = 2

    def calculate_mean(self, values: list[float]) -> float:
        """Calculate mean of values."""
        return sum(values) / len(values) if values else 0.0

    def calculate_std_dev(self, values: list[float]) -> float:
        """Calculate standard deviation of values."""
        if not values:
            return 0.0
        mean = self.calculate_mean(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

    def calculate_bollinger_bands(self, prices: list[float]) -> BollingerBandsResult:
        """Calculate Bollinger Bands for given price series."""
        if len(prices) < self.period:
            # Return default values if not enough data
            return BollingerBandsResult(
                upper=prices[-1] if prices else 0.0,
                middle=prices[-1] if prices else 0.0,
                lower=prices[-1] if prices else 0.0,
                bandwidth=0.0,
                percent_b=0.5,
            )

        recent_prices = prices[-self.period:]
        middle = self.calculate_mean(recent_prices)
        std = self.calculate_std_dev(recent_prices)
        
        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)
        
        current_price = prices[-1]
        bandwidth = (upper - lower) / middle if middle != 0 else 0.0
        percent_b = (current_price - lower) / (upper - lower) if (upper - lower) != 0 else 0.5
        
        return BollingerBandsResult(
            upper=upper,
            middle=middle,
            lower=lower,
            bandwidth=bandwidth,
            percent_b=percent_b,
        )

    def generate_signal(self, ticker: str) -> SignalRecord | None:
        """Generate Bollinger Bands signal for a ticker."""
        try:
            prices = self.db.get_prices(ticker, limit=self.period + 10)
            if len(prices) < self.period:
                logger.warning("Not enough price data for Bollinger Bands: %s", ticker)
                return None

            close_prices = [p.close for p in prices]
            bb = self.calculate_bollinger_bands(close_prices)
            
            current_price = close_prices[-1]
            
            # Signal generation logic
            signal_type = None
            strength = 1
            
            if bb.percent_b < 0.2:  # Near lower band - potential buy
                signal_type = "BUY"
                strength = 2 if bb.percent_b < 0.1 else 1
            elif bb.percent_b > 0.8:  # Near upper band - potential sell
                signal_type = "SELL"
                strength = 2 if bb.percent_b > 0.9 else 1
            
            if signal_type is None:
                return None

            signal = SignalRecord(
                ticker=ticker,
                signal_type=signal_type,
                rsi=50.0,  # Placeholder for RSI
                price=current_price,
                signal_date=prices[-1].date,
                created_at=SignalDatabase.now_iso(),
                strategy="BOLLINGER",
                strength=strength,
            )
            
            return signal

        except Exception as e:
            logger.error("Error generating Bollinger Bands signal for %s: %s", ticker, e)
            return None

    def generate_all(self) -> list[SignalRecord]:
        """Generate Bollinger Bands signals for all tickers."""
        signals = []
        for ticker in self.settings.tickers:
            signal = self.generate_signal(ticker)
            if signal:
                signals.append(signal)
        
        # Save to database
        for signal in signals:
            self.db.insert_signal(signal)
        
        logger.info("Bollinger Bands signals generated: %d", len(signals))
        return signals
