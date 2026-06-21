from __future__ import annotations


def calculate_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Wilder's RSI. Returns a list aligned with closes (None until enough data)."""
    if period < 1 or len(closes) < period + 1:
        return [None] * len(closes)

    rsi_values: list[float | None] = [None] * len(closes)
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values[period] = _to_rsi(avg_gain, avg_loss)

    for i in range(period, len(changes)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        rsi_values[i + 1] = _to_rsi(avg_gain, avg_loss)

    return rsi_values


def latest_rsi(closes: list[float], period: int = 14) -> float | None:
    values = calculate_rsi(closes, period)
    if not values:
        return None
    return values[-1]


def _to_rsi(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 0.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
