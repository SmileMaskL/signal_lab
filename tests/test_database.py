from config.settings import Settings
from database.db import SignalDatabase, SignalRecord
from pathlib import Path


def test_signal_deduplication(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = SignalDatabase(db_path)

    signal = SignalRecord(
        ticker="SPY",
        signal_type="BUY",
        strategy="RSI",
        rsi=28.5,
        price=450.0,
        signal_date="2026-06-01",
        created_at=SignalDatabase.now_iso(),
        sent=0,
    )

    first_id = db.insert_signal(signal)
    second_id = db.insert_signal(signal)

    assert first_id is not None
    assert second_id is None


def test_subscriber_management(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = SignalDatabase(db_path)

    sub = db.upsert_subscriber(12345, "FREE", "testuser")
    assert sub.chat_id == 12345
    assert sub.tier == "FREE"

    premium = db.upsert_subscriber(12345, "PREMIUM", "testuser")
    assert premium.tier == "PREMIUM"

    counts = db.subscriber_count()
    assert counts["PREMIUM"] == 1
