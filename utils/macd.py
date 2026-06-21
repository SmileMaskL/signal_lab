from __future__ import annotations


def ema_series(values: list[float], period: int) -> list[float | None]:
    if period < 1 or len(values) < period:
        return [None] * len(values)

    result: list[float | None] = [None] * len(values)
    sma = sum(values[:period]) / period
    result[period - 1] = sma
    multiplier = 2.0 / (period + 1)

    for i in range(period, len(values)):
        prev = result[i - 1]
        if prev is None:
            continue
        result[i] = (values[i] - prev) * multiplier + prev

    return result


def calculate_macd(
    closes: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None]]:
    ema_fast = ema_series(closes, fast_period)
    ema_slow = ema_series(closes, slow_period)

    macd_line: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    valid_indices = [i for i, value in enumerate(macd_line) if value is not None]
    signal_line: list[float | None] = [None] * len(closes)

    if len(valid_indices) >= signal_period:
        macd_values = [macd_line[i] for i in valid_indices]
        signal_ema = ema_series(macd_values, signal_period)
        for idx, signal_value in zip(valid_indices, signal_ema):
            if signal_value is not None:
                signal_line[idx] = signal_value

    return macd_line, signal_line


def detect_macd_cross(
    macd_line: list[float | None],
    signal_line: list[float | None],
) -> str | None:
    if len(macd_line) < 2:
        return None

    prev_macd = macd_line[-2]
    curr_macd = macd_line[-1]
    prev_signal = signal_line[-2]
    curr_signal = signal_line[-1]

    if None in (prev_macd, curr_macd, prev_signal, curr_signal):
        return None

    if prev_macd <= prev_signal and curr_macd > curr_signal:
        return "BUY"
    if prev_macd >= prev_signal and curr_macd < curr_signal:
        return "SELL"
    return None
