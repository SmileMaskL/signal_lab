from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Iterable


@dataclass
class PriceRecord:
    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class SignalRecord:
    ticker: str
    signal_type: str
    rsi: float
    price: float
    signal_date: str
    created_at: str
    sent: int = 0
    id: int | None = None
    strategy: str = "RSI"
    macd_line: float | None = None
    macd_signal_line: float | None = None
    strength: int = 1


@dataclass
class SubscriberRecord:
    chat_id: int
    username: str | None
    tier: str
    subscribed_at: str
    active: int = 1
    id: int | None = None
    referral_code: str = ""
    referred_by: int | None = None
    trial_expires_at: str | None = None
    premium_expires_at: str | None = None
    weekly_signal_count: int = 0
    week_start: str | None = None


class SignalDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    UNIQUE(ticker, date)
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    strategy TEXT NOT NULL DEFAULT 'RSI',
                    rsi REAL NOT NULL,
                    macd_line REAL,
                    macd_signal_line REAL,
                    price REAL NOT NULL,
                    signal_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent INTEGER NOT NULL DEFAULT 0,
                    strength INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(ticker, signal_type, signal_date, strategy)
                );

                CREATE TABLE IF NOT EXISTS subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    tier TEXT NOT NULL DEFAULT 'FREE',
                    subscribed_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    total_signals INTEGER NOT NULL,
                    win_count INTEGER NOT NULL,
                    loss_count INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    avg_return_pct REAL NOT NULL,
                    run_date TEXT NOT NULL,
                    UNIQUE(ticker, strategy, run_date)
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_chat_id INTEGER NOT NULL,
                    referred_chat_id INTEGER NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    tier TEXT NOT NULL,
                    amount_krw INTEGER NOT NULL,
                    payment_method TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_engagement (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL UNIQUE,
                    last_check_in TEXT,
                    check_in_streak INTEGER DEFAULT 0,
                    total_check_ins INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._migrate_signals_table(conn)
            self._migrate_subscribers_table(conn)
            self._migrate_engagement_table(conn)

    def _migrate_signals_table(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(signals)").fetchall()}
        if "strategy" not in columns:
            conn.executescript(
                """
                ALTER TABLE signals RENAME TO signals_old;
                CREATE TABLE signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    strategy TEXT NOT NULL DEFAULT 'RSI',
                    rsi REAL NOT NULL,
                    macd_line REAL,
                    macd_signal_line REAL,
                    price REAL NOT NULL,
                    signal_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent INTEGER NOT NULL DEFAULT 0,
                    strength INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(ticker, signal_type, signal_date, strategy)
                );
                INSERT INTO signals (
                    id, ticker, signal_type, strategy, rsi, macd_line, macd_signal_line,
                    price, signal_date, created_at, sent, strength
                )
                SELECT id, ticker, signal_type, 'RSI', rsi, NULL, NULL,
                    price, signal_date, created_at, sent, 1
                FROM signals_old;
                DROP TABLE signals_old;
                """
            )
        elif "strength" not in columns:
            conn.execute("ALTER TABLE signals ADD COLUMN strength INTEGER NOT NULL DEFAULT 1")

    def _migrate_subscribers_table(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(subscribers)").fetchall()}
        migrations = {
            "referral_code": "ALTER TABLE subscribers ADD COLUMN referral_code TEXT DEFAULT ''",
            "referred_by": "ALTER TABLE subscribers ADD COLUMN referred_by INTEGER",
            "trial_expires_at": "ALTER TABLE subscribers ADD COLUMN trial_expires_at TEXT",
            "premium_expires_at": "ALTER TABLE subscribers ADD COLUMN premium_expires_at TEXT",
            "weekly_signal_count": "ALTER TABLE subscribers ADD COLUMN weekly_signal_count INTEGER NOT NULL DEFAULT 0",
            "week_start": "ALTER TABLE subscribers ADD COLUMN week_start TEXT",
        }
        for col, sql in migrations.items():
            if col not in columns:
                conn.execute(sql)

    def _migrate_engagement_table(self, conn: sqlite3.Connection) -> None:
        """Create user_engagement table if it doesn't exist."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_engagement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL UNIQUE,
                last_check_in TEXT,
                check_in_streak INTEGER DEFAULT 0,
                total_check_ins INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _row_to_subscriber(row: sqlite3.Row) -> SubscriberRecord:
        keys = row.keys()
        return SubscriberRecord(
            id=row["id"],
            chat_id=row["chat_id"],
            username=row["username"],
            tier=row["tier"],
            subscribed_at=row["subscribed_at"],
            active=row["active"],
            referral_code=row["referral_code"] if "referral_code" in keys else "",
            referred_by=row["referred_by"] if "referred_by" in keys else None,
            trial_expires_at=row["trial_expires_at"] if "trial_expires_at" in keys else None,
            premium_expires_at=row["premium_expires_at"] if "premium_expires_at" in keys else None,
            weekly_signal_count=row["weekly_signal_count"] if "weekly_signal_count" in keys else 0,
            week_start=row["week_start"] if "week_start" in keys else None,
        )

    def upsert_prices(self, records: Iterable[PriceRecord]) -> int:
        rows = [
            (r.ticker, r.date, r.open, r.high, r.low, r.close, r.volume)
            for r in records
        ]
        if not rows:
            return 0

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO stock_prices (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
                """,
                rows,
            )
        return len(rows)

    def get_prices(self, ticker: str, limit: int = 200) -> list[PriceRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ticker, date, open, high, low, close, volume
                FROM stock_prices
                WHERE ticker = ?
                ORDER BY date ASC
                LIMIT ?
                """,
                (ticker, limit),
            ).fetchall()

        return [
            PriceRecord(
                ticker=row["ticker"],
                date=row["date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]

    def insert_signal(self, signal: SignalRecord) -> int | None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO signals (
                    ticker, signal_type, strategy, rsi, macd_line, macd_signal_line,
                    price, signal_date, created_at, sent, strength
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.ticker,
                    signal.signal_type,
                    signal.strategy,
                    signal.rsi,
                    signal.macd_line,
                    signal.macd_signal_line,
                    signal.price,
                    signal.signal_date,
                    signal.created_at,
                    signal.sent,
                    signal.strength,
                ),
            )
            if cursor.rowcount == 0:
                return None
            return int(cursor.lastrowid)

    def get_unsent_signals(self) -> list[SignalRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, ticker, signal_type, strategy, rsi, macd_line, macd_signal_line,
                    price, signal_date, created_at, sent, strength
                FROM signals
                WHERE sent = 0
                ORDER BY created_at ASC
                """
            ).fetchall()

        return [self._row_to_signal(row) for row in rows]

    def get_signals_by_date(self, signal_date: str, ticker: str | None = None) -> list[SignalRecord]:
        query = """
            SELECT
                id, ticker, signal_type, strategy, rsi, macd_line, macd_signal_line,
                price, signal_date, created_at, sent, strength
            FROM signals
            WHERE signal_date = ?
        """
        params: list[str] = [signal_date]
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        query += " ORDER BY created_at ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_signal(row) for row in rows]

    def get_recent_signals(self, limit: int = 20) -> list[SignalRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, ticker, signal_type, strategy, rsi, macd_line, macd_signal_line,
                    price, signal_date, created_at, sent, strength
                FROM signals
                ORDER BY signal_date DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_signal(row) for row in rows]

    def mark_signal_sent(self, signal_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE signals SET sent = 1 WHERE id = ?", (signal_id,))

    def upsert_subscriber(
        self,
        chat_id: int,
        tier: str,
        username: str | None = None,
        referral_code: str | None = None,
        referred_by: int | None = None,
        trial_expires_at: str | None = None,
        premium_expires_at: str | None = None,
    ) -> SubscriberRecord:
        now = self.now_iso()
        code = referral_code or f"SL{chat_id}"
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT chat_id FROM subscribers WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE subscribers SET
                        username = COALESCE(?, username),
                        tier = ?,
                        active = 1,
                        trial_expires_at = COALESCE(?, trial_expires_at),
                        premium_expires_at = COALESCE(?, premium_expires_at)
                    WHERE chat_id = ?
                    """,
                    (username, tier, trial_expires_at, premium_expires_at, chat_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO subscribers (
                        chat_id, username, tier, subscribed_at, active,
                        referral_code, referred_by, trial_expires_at, premium_expires_at,
                        weekly_signal_count, week_start
                    )
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        chat_id, username, tier, now, code, referred_by,
                        trial_expires_at, premium_expires_at, now[:10],
                    ),
                )

            row = conn.execute(
                """
                SELECT id, chat_id, username, tier, subscribed_at, active,
                       referral_code, referred_by, trial_expires_at, premium_expires_at,
                       weekly_signal_count, week_start
                FROM subscribers WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
        return self._row_to_subscriber(row)

    def deactivate_subscriber(self, chat_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE subscribers SET active = 0 WHERE chat_id = ?",
                (chat_id,),
            )
            return cursor.rowcount > 0

    def get_subscriber(self, chat_id: int) -> SubscriberRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, chat_id, username, tier, subscribed_at, active,
                       referral_code, referred_by, trial_expires_at, premium_expires_at,
                       weekly_signal_count, week_start
                FROM subscribers WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_subscriber(row)

    def get_subscriber_by_referral_code(self, code: str) -> SubscriberRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, chat_id, username, tier, subscribed_at, active,
                       referral_code, referred_by, trial_expires_at, premium_expires_at,
                       weekly_signal_count, week_start
                FROM subscribers WHERE referral_code = ? AND active = 1
                """,
                (code.strip().upper(),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_subscriber(row)

    def get_active_subscribers(self, tier: str | None = None) -> list[SubscriberRecord]:
        query = """
            SELECT id, chat_id, username, tier, subscribed_at, active,
                   referral_code, referred_by, trial_expires_at, premium_expires_at,
                   weekly_signal_count, week_start
            FROM subscribers WHERE active = 1
        """
        params: list[str] = []
        if tier:
            query += " AND tier = ?"
            params.append(tier)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_subscriber(row) for row in rows]

    def get_free_subscribers(self) -> list[SubscriberRecord]:
        """Active subscribers who are effectively on FREE tier."""
        return [
            sub
            for sub in self.get_active_subscribers()
            if sub.tier == "FREE"
        ]

    def subscriber_count(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT tier, COUNT(*) AS cnt
                FROM subscribers
                WHERE active = 1
                GROUP BY tier
                """
            ).fetchall()
        counts = {"FREE": 0, "PREMIUM": 0, "VIP": 0}
        for row in rows:
            tier = row["tier"]
            if tier in counts:
                counts[tier] = row["cnt"]
            else:
                counts[tier] = row["cnt"]
        return counts

    def increment_weekly_signal(self, chat_id: int) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_start_str = week_start.strftime("%Y-%m-%d")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT week_start, weekly_signal_count FROM subscribers WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            if row is None:
                return 0

            count = row["weekly_signal_count"]
            if row["week_start"] != week_start_str:
                count = 0

            count += 1
            conn.execute(
                """
                UPDATE subscribers SET weekly_signal_count = ?, week_start = ?
                WHERE chat_id = ?
                """,
                (count, week_start_str, chat_id),
            )
        return count

    def get_weekly_signal_count(self, chat_id: int) -> int:
        week_start_str = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT week_start, weekly_signal_count FROM subscribers WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if row is None:
            return 0
        if row["week_start"] != week_start_str:
            return 0
        return row["weekly_signal_count"]

    def record_referral(self, referrer_chat_id: int, referred_chat_id: int) -> bool:
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO referrals (referrer_chat_id, referred_chat_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (referrer_chat_id, referred_chat_id, self.now_iso()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def referral_count(self, chat_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM referrals WHERE referrer_chat_id = ?",
                (chat_id,),
            ).fetchone()
        return row["cnt"] if row else 0

    def get_top_referrers(self, limit: int = 10) -> list[tuple[str | None, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.username, COUNT(r.referred_chat_id) as referral_count
                FROM subscribers s
                LEFT JOIN referrals r ON s.chat_id = r.referrer_chat_id
                WHERE s.active = 1
                GROUP BY s.chat_id, s.username
                ORDER BY referral_count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [(row["username"], row["referral_count"]) for row in rows]

    def record_payment(
        self,
        chat_id: int,
        tier: str,
        amount_krw: int,
        payment_method: str = "manual",
        note: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO payments (chat_id, tier, amount_krw, payment_method, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, tier, amount_krw, payment_method, note, self.now_iso()),
            )

    def revenue_stats(self) -> dict[str, int | float]:
        from config.settings import settings

        with self._connect() as conn:
            total_row = conn.execute(
                "SELECT COALESCE(SUM(amount_krw), 0) AS total FROM payments"
            ).fetchone()
            month_row = conn.execute(
                """
                SELECT COALESCE(SUM(amount_krw), 0) AS total FROM payments
                WHERE created_at >= date('now', 'start of month')
                """
            ).fetchone()
            referral_row = conn.execute("SELECT COUNT(*) AS cnt FROM referrals").fetchone()
            trial_row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM subscribers
                WHERE active = 1 AND trial_expires_at IS NOT NULL
                AND trial_expires_at > datetime('now')
                """
            ).fetchone()

        counts = self.subscriber_count()
        mrr = (
            counts.get("PREMIUM", 0) * settings.premium_price_krw
            + counts.get("VIP", 0) * settings.vip_price_krw
        )

        # Calculate conversion metrics
        total_subscribers = sum(counts.values())
        conversion_rate = 0
        if total_subscribers > 0:
            conversion_rate = ((counts.get("PREMIUM", 0) + counts.get("VIP", 0)) / total_subscribers) * 100

        # Calculate LTV (Lifetime Value) - simplified
        avg_revenue_per_user = 0
        if total_subscribers > 0:
            avg_revenue_per_user = (total_row["total"] if total_row else 0) / total_subscribers

        # Calculate churn rate (simplified - users who became inactive in last 30 days)
        churn_rate = 0.0
        with self._connect() as conn:
            inactive_row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM subscribers
                WHERE active = 0 AND subscribed_at >= date('now', '-30 days')
                """
            ).fetchone()
            if total_subscribers > 0:
                churn_rate = (inactive_row["cnt"] / total_subscribers) * 100 if inactive_row else 0

        return {
            "total_revenue_krw": total_row["total"] if total_row else 0,
            "month_revenue_krw": month_row["total"] if month_row else 0,
            "estimated_mrr_krw": mrr,
            "referral_count": referral_row["cnt"] if referral_row else 0,
            "active_trials": trial_row["cnt"] if trial_row else 0,
            "free_count": counts.get("FREE", 0),
            "premium_count": counts.get("PREMIUM", 0),
            "vip_count": counts.get("VIP", 0),
            "conversion_rate": round(conversion_rate, 2),
            "avg_ltv_krw": round(avg_revenue_per_user, 2),
            "churn_rate": round(churn_rate, 2),
        }

    def count_premium_signals_since(self, since_date: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM signals
                WHERE signal_date >= ? AND strategy IN ('MACD', 'CONFLUENCE')
                """,
                (since_date,),
            ).fetchone()
        return row["cnt"] if row else 0

    def save_backtest_result(
        self,
        ticker: str,
        strategy: str,
        total_signals: int,
        win_count: int,
        loss_count: int,
        win_rate: float,
        avg_return_pct: float,
        run_date: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_results (
                    ticker, strategy, total_signals, win_count, loss_count,
                    win_rate, avg_return_pct, run_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, strategy, run_date) DO UPDATE SET
                    total_signals = excluded.total_signals,
                    win_count = excluded.win_count,
                    loss_count = excluded.loss_count,
                    win_rate = excluded.win_rate,
                    avg_return_pct = excluded.avg_return_pct
                """,
                (
                    ticker,
                    strategy,
                    total_signals,
                    win_count,
                    loss_count,
                    win_rate,
                    avg_return_pct,
                    run_date,
                ),
            )

    def get_latest_backtest_results(self, strategy: str | None = None) -> list[sqlite3.Row]:
        query = """
            SELECT ticker, strategy, total_signals, win_count, loss_count,
                   win_rate, avg_return_pct, run_date
            FROM backtest_results
            WHERE run_date = (SELECT MAX(run_date) FROM backtest_results)
        """
        params: list[str] = []
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        query += " ORDER BY ticker ASC"

        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> SignalRecord:
        return SignalRecord(
            id=row["id"],
            ticker=row["ticker"],
            signal_type=row["signal_type"],
            strategy=row["strategy"],
            rsi=row["rsi"],
            macd_line=row["macd_line"],
            macd_signal_line=row["macd_signal_line"],
            price=row["price"],
            signal_date=row["signal_date"],
            created_at=row["created_at"],
            sent=row["sent"],
            strength=row["strength"],
        )

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def record_check_in(self, chat_id: int) -> dict[str, int]:
        """Record user check-in and return streak info."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        with self._connect() as conn:
            # Get existing engagement data
            row = conn.execute(
                "SELECT last_check_in, check_in_streak, total_check_ins, points FROM user_engagement WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            
            if row is None:
                # First check-in
                conn.execute(
                    """
                    INSERT INTO user_engagement (chat_id, last_check_in, check_in_streak, total_check_ins, points, created_at)
                    VALUES (?, ?, 1, 1, 10, ?)
                    """,
                    (chat_id, today, self.now_iso()),
                )
                return {"streak": 1, "total": 1, "points": 10, "bonus": 0}
            
            last_check = row["last_check_in"]
            streak = row["check_in_streak"]
            total = row["total_check_ins"]
            points = row["points"]
            
            # Check if already checked in today
            if last_check == today:
                return {"streak": streak, "total": total, "points": points, "bonus": 0}
            
            # Calculate streak
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_check == yesterday:
                streak += 1
            else:
                streak = 1
            
            total += 1
            bonus_points = 0
            
            # Streak bonuses
            if streak % 7 == 0:  # Weekly bonus
                bonus_points = 30
            elif streak % 30 == 0:  # Monthly bonus
                bonus_points = 100
            
            points += 10 + bonus_points
            
            conn.execute(
                """
                UPDATE user_engagement
                SET last_check_in = ?, check_in_streak = ?, total_check_ins = ?, points = ?
                WHERE chat_id = ?
                """,
                (today, streak, total, points, chat_id),
            )
            
            return {"streak": streak, "total": total, "points": points, "bonus": bonus_points}

    def get_engagement_stats(self, chat_id: int) -> dict[str, int] | None:
        """Get user engagement statistics."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT check_in_streak, total_check_ins, points FROM user_engagement WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        
        if row is None:
            return None
        
        return {
            "streak": row["check_in_streak"],
            "total": row["total_check_ins"],
            "points": row["points"],
        }

    def get_top_engaged_users(self, limit: int = 10) -> list[tuple[int, int]]:
        """Get top users by engagement points."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chat_id, points
                FROM user_engagement
                ORDER BY points DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [(row["chat_id"], row["points"]) for row in rows]
