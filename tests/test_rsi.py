from utils.rsi import calculate_rsi, latest_rsi


def test_rsi_range():
    closes = [float(i) for i in range(1, 31)]
    values = calculate_rsi(closes, period=14)
    last = values[-1]
    assert last is not None
    assert 0 <= last <= 100


def test_rsi_oversold():
    closes = [100.0] * 20 + [99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0]
    rsi = latest_rsi(closes, period=14)
    assert rsi is not None
    assert rsi < 50


def test_rsi_insufficient_data():
    closes = [100.0, 101.0, 102.0]
    assert latest_rsi(closes, period=14) is None
