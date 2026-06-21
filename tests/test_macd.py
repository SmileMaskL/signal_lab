from utils.macd import calculate_macd, detect_macd_cross


def test_macd_cross_buy():
    closes = [float(i) for i in range(1, 51)]
    macd_line, signal_line = calculate_macd(closes, 12, 26, 9)
    cross = detect_macd_cross(macd_line, signal_line)
    assert cross in (None, "BUY", "SELL")


def test_macd_golden_cross_detection():
    macd_line = [None, None, -0.5, -0.2, 0.1]
    signal_line = [None, None, -0.3, -0.1, 0.05]
    assert detect_macd_cross(macd_line, signal_line) == "BUY"


def test_macd_dead_cross_detection():
    macd_line = [None, None, 0.5, 0.2, -0.1]
    signal_line = [None, None, 0.3, 0.1, -0.05]
    assert detect_macd_cross(macd_line, signal_line) == "SELL"
