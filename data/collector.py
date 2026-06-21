from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import requests

from config.settings import Settings
from database.db import PriceRecord, SignalDatabase

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


class StockCollector:
    def __init__(self, settings: Settings, db: SignalDatabase) -> None:
        self.settings = settings
        self.db = db

    def collect_all(self) -> int:
        total = 0
        for ticker in self.settings.tickers:
            total += self.collect_ticker(ticker)
        return total

    def collect_ticker(self, ticker: str) -> int:
        start = datetime.now() - timedelta(days=self.settings.history_days)
        end = datetime.now()
        logger.info("Collecting data: %s (from %s)", ticker, start.date())

        for attempt in range(1, self.settings.api_retry_count + 1):
            try:
                records = self._fetch_from_yahoo(ticker, start, end)
                if not records:
                    logger.warning("No data returned for %s", ticker)
                    return 0
                saved = self.db.upsert_prices(records)
                logger.info("Saved %d rows for %s", saved, ticker)
                return saved
            except Exception:
                logger.exception(
                    "Failed to download data for %s (attempt %d/%d)",
                    ticker,
                    attempt,
                    self.settings.api_retry_count,
                )
                if attempt < self.settings.api_retry_count:
                    time.sleep(self.settings.api_retry_delay)
        return 0

    def _fetch_from_yahoo(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
    ) -> list[PriceRecord]:
        params = {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "includeAdjustedClose": "true",
        }
        response = requests.get(
            YAHOO_CHART_URL.format(ticker=ticker),
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        results = payload.get("chart", {}).get("result") or []
        if not results:
            error = payload.get("chart", {}).get("error")
            raise ValueError(f"Yahoo Finance returned no data for {ticker}: {error}")

        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]

        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        records: list[PriceRecord] = []
        for idx, ts in enumerate(timestamps):
            close = closes[idx] if idx < len(closes) else None
            if close is None:
                continue

            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            volume = volumes[idx] if idx < len(volumes) and volumes[idx] is not None else 0

            records.append(
                PriceRecord(
                    ticker=ticker,
                    date=date_str,
                    open=float(opens[idx]) if idx < len(opens) and opens[idx] is not None else float(close),
                    high=float(highs[idx]) if idx < len(highs) and highs[idx] is not None else float(close),
                    low=float(lows[idx]) if idx < len(lows) and lows[idx] is not None else float(close),
                    close=float(close),
                    volume=int(volume),
                )
            )

        return records
