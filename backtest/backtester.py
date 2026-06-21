from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from config.settings import Settings
from database.db import PriceRecord, SignalDatabase
from utils.macd import calculate_macd, detect_macd_cross
from utils.rsi import calculate_rsi

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    ticker: str
    strategy: str
    total_signals: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_return_pct: float


class Backtester:
    """Historical signal simulation for credibility and premium marketing."""

    def __init__(self, settings: Settings, db: SignalDatabase) -> None:
        self.settings = settings
        self.db = db

    def run_all(self) -> list[BacktestResult]:
        run_date = datetime.now().strftime("%Y-%m-%d")
        results: list[BacktestResult] = []

        for ticker in self.settings.tickers:
            for strategy in ("RSI", "MACD", "CONFLUENCE"):
                result = self.run_strategy(ticker, strategy)
                if result.total_signals == 0:
                    continue
                results.append(result)
                self.db.save_backtest_result(
                    ticker=result.ticker,
                    strategy=result.strategy,
                    total_signals=result.total_signals,
                    win_count=result.win_count,
                    loss_count=result.loss_count,
                    win_rate=result.win_rate,
                    avg_return_pct=result.avg_return_pct,
                    run_date=run_date,
                )
                logger.info(
                    "%s %s backtest: %d signals, win rate %.1f%%, avg return %.2f%%",
                    ticker,
                    strategy,
                    result.total_signals,
                    result.win_rate,
                    result.avg_return_pct,
                )
        return results

    def run_strategy(self, ticker: str, strategy: str) -> BacktestResult:
        prices = self.db.get_prices(ticker, limit=self.settings.backtest_days + 50)
        if len(prices) < self.settings.rsi_period + 2:
            return BacktestResult(ticker, strategy, 0, 0, 0, 0.0, 0.0)

        signals = self._generate_historical_signals(prices, strategy)
        wins = 0
        losses = 0
        returns: list[float] = []

        for idx in signals:
            entry = prices[idx].close
            exit_idx = min(idx + self.settings.backtest_hold_days, len(prices) - 1)
            exit_price = prices[exit_idx].close
            signal_type = signals[idx]

            if signal_type == "BUY":
                ret = ((exit_price - entry) / entry) * 100
            else:
                ret = ((entry - exit_price) / entry) * 100

            returns.append(ret)
            if ret > 0:
                wins += 1
            else:
                losses += 1

        total = wins + losses
        win_rate = (wins / total * 100) if total else 0.0
        avg_return = sum(returns) / len(returns) if returns else 0.0

        return BacktestResult(
            ticker=ticker,
            strategy=strategy,
            total_signals=total,
            win_count=wins,
            loss_count=losses,
            win_rate=round(win_rate, 2),
            avg_return_pct=round(avg_return, 2),
        )

    def _generate_historical_signals(
        self,
        prices: list[PriceRecord],
        strategy: str,
    ) -> dict[int, str]:
        closes = [p.close for p in prices]
        signals: dict[int, str] = {}

        if strategy in ("RSI", "CONFLUENCE"):
            rsi_values = calculate_rsi(closes, self.settings.rsi_period)
            for i, rsi in enumerate(rsi_values):
                if rsi is None:
                    continue
                if rsi <= self.settings.rsi_buy_threshold:
                    signals[i] = "BUY"
                elif rsi >= self.settings.rsi_sell_threshold:
                    signals[i] = "SELL"

        if strategy == "MACD":
            macd_line, signal_line = calculate_macd(
                closes,
                self.settings.macd_fast_period,
                self.settings.macd_slow_period,
                self.settings.macd_signal_period,
            )
            for i in range(1, len(closes)):
                cross = detect_macd_cross(macd_line[: i + 1], signal_line[: i + 1])
                if cross:
                    signals[i] = cross

        if strategy == "CONFLUENCE":
            macd_line, signal_line = calculate_macd(
                closes,
                self.settings.macd_fast_period,
                self.settings.macd_slow_period,
                self.settings.macd_signal_period,
            )
            confluence: dict[int, str] = {}
            for i in range(1, len(closes)):
                rsi = rsi_values[i] if i < len(rsi_values) else None
                cross = detect_macd_cross(macd_line[: i + 1], signal_line[: i + 1])
                if cross == "BUY" and rsi is not None and rsi <= self.settings.rsi_buy_threshold:
                    confluence[i] = "BUY"
                elif cross == "SELL" and rsi is not None and rsi >= self.settings.rsi_sell_threshold:
                    confluence[i] = "SELL"
            return confluence

        return signals

    @staticmethod
    def format_summary(results: list) -> str:
        if not results:
            return "백테스트 데이터가 없습니다. 먼저 <code>python main.py --backtest</code> 를 실행하세요."

        lines = ["📊 <b>Signal Lab 백테스트 성과</b>\n"]
        for row in results:
            lines.append(
                f"<b>{row['ticker']}</b> [{row['strategy']}]\n"
                f"  신호 {row['total_signals']}건 | 승률 {row['win_rate']:.1f}% | "
                f"평균수익 {row['avg_return_pct']:+.2f}%\n"
            )
        lines.append(f"\n<i>보유기간 {results[0]['run_date'] if hasattr(results[0], 'keys') else ''}</i>")
        return "\n".join(lines)
