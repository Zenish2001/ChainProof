"""
data/database.py

SQLite storage for the paper trading bot: daily price candles, trades,
signals, open positions and periodic account snapshots.

The database file lives in STATE_DIR (default: data/), which can be pointed
at a mounted volume so history survives container restarts.
"""

import os
import sqlite3
from datetime import datetime

import pandas as pd

STATE_DIR = os.environ.get("STATE_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("BOT_DB_PATH", os.path.join(STATE_DIR, "trading_bot.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    symbol    TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open      REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, timestamp)
);
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    trade_type  TEXT NOT NULL,          -- BUY or SELL
    quantity    REAL NOT NULL,
    price       REAL NOT NULL,
    total_value REAL NOT NULL,
    fees        REAL DEFAULT 0,
    status      TEXT DEFAULT 'FILLED',
    strategy    TEXT,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    indicator_name  TEXT,
    signal_strength REAL,
    price           REAL
);
CREATE TABLE IF NOT EXISTS portfolio (
    symbol        TEXT PRIMARY KEY,
    quantity      REAL NOT NULL,
    avg_buy_price REAL NOT NULL,
    current_price REAL,
    last_updated  TEXT
);
CREATE TABLE IF NOT EXISTS performance_metrics (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp                 TEXT NOT NULL,
    total_portfolio_value     REAL NOT NULL,
    cash                      REAL,
    total_profit_loss         REAL,
    total_profit_loss_percent REAL
);
CREATE TABLE IF NOT EXISTS decisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    price      REAL,
    signal     TEXT,
    buy_votes  INTEGER, sell_votes INTEGER, hold_votes INTEGER,
    action     TEXT,                -- BUY, SELL, STOP_LOSS, TAKE_PROFIT, HOLD, IN_POSITION, WAIT
    source     TEXT DEFAULT 'live'  -- 'replay' (warm start) or 'live'
);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades (timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_time ON decisions (timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON performance_metrics (timestamp);
"""


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


class TradingDatabase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # Columns added after the first version; add them to old files.
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(trades)")}
            for name, decl in (("source", "TEXT DEFAULT 'live'"), ("pnl", "REAL"), ("pnl_pct", "REAL")):
                if name not in cols:
                    conn.execute(f"ALTER TABLE trades ADD COLUMN {name} {decl}")
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(performance_metrics)")}
            if "source" not in cols:
                conn.execute("ALTER TABLE performance_metrics ADD COLUMN source TEXT DEFAULT 'live'")

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------- prices
    def insert_price_data(self, symbol, df):
        """Store OHLCV candles. Accepts 'Close' or 'close' style columns and
        a datetime index; existing candles for the same day are replaced."""
        if df is None or df.empty:
            return 0
        frame = df.rename(columns=str.lower)
        rows = []
        for ts, r in frame.iterrows():
            stamp = pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            rows.append((symbol, stamp, float(r.get("open", r["close"])), float(r.get("high", r["close"])),
                         float(r.get("low", r["close"])), float(r["close"]), float(r.get("volume", 0) or 0)))
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO price_history (symbol, timestamp, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        return len(rows)

    def get_price_data(self, symbol, limit=None, start_date=None):
        """Candles for a symbol, oldest first, with lowercase OHLCV columns.
        start_date ('YYYY-MM-DD') keeps only candles on or after that day."""
        sql = "SELECT timestamp, open, high, low, close, volume FROM price_history WHERE symbol = ?"
        params = [symbol]
        if start_date:
            sql += " AND timestamp >= ?"
            params.append(str(start_date))
        sql += " ORDER BY timestamp"
        with self._connect() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        return df.tail(limit) if limit else df

    def latest_candle_time(self, symbol):
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(timestamp) AS t FROM price_history WHERE symbol = ?", (symbol,)).fetchone()
        return pd.Timestamp(row["t"]) if row and row["t"] else None

    # ------------------------------------------------------------- trades
    def insert_trade(self, symbol, trade_type, quantity, price, strategy=None, notes=None, fees=0.0,
                     timestamp=None, source="live", pnl=None, pnl_pct=None):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trades (symbol, timestamp, trade_type, quantity, price, total_value, fees, strategy, "
                "notes, source, pnl, pnl_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (symbol, timestamp or _now(), trade_type, float(quantity), float(price),
                 float(quantity) * float(price), float(fees), strategy, notes, source,
                 None if pnl is None else float(pnl), None if pnl_pct is None else float(pnl_pct)))

    def count_trades(self):
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

    def insert_decision(self, symbol, price, signal, votes, action, source="live", timestamp=None):
        b = sum(1 for v in votes if v == "BUY")
        s = sum(1 for v in votes if v == "SELL")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO decisions (timestamp, symbol, price, signal, buy_votes, sell_votes, hold_votes, action, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (timestamp or _now(), symbol, float(price), signal, b, s, len(votes) - b - s, action, source))
            # keep the log bounded
            conn.execute("DELETE FROM decisions WHERE id <= (SELECT MAX(id) FROM decisions) - 5000")

    def get_decisions(self, limit=40):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_trades(self, limit=50):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def insert_signal(self, symbol, signal_type, indicator_name, signal_strength, price):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO signals (symbol, timestamp, signal_type, indicator_name, signal_strength, price) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (symbol, _now(), signal_type, indicator_name, float(signal_strength), float(price)))

    # ---------------------------------------------------------- portfolio
    def set_positions(self, positions, prices):
        """Mirror the bot's open positions into the portfolio table."""
        with self._connect() as conn:
            conn.execute("DELETE FROM portfolio")
            for symbol, p in positions.items():
                conn.execute(
                    "INSERT INTO portfolio (symbol, quantity, avg_buy_price, current_price, last_updated) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (symbol, float(p["quantity"]), float(p["entry_price"]),
                     float(prices.get(symbol) or p["entry_price"]), _now()))

    def get_portfolio(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM portfolio WHERE quantity > 0").fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------- snapshots
    def record_snapshot(self, total_value, cash, initial_capital, timestamp=None, source="live"):
        pnl = total_value - initial_capital
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO performance_metrics (timestamp, total_portfolio_value, cash, total_profit_loss, "
                "total_profit_loss_percent, source) VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp or _now(), float(total_value), float(cash), float(pnl),
                 float(pnl / initial_capital * 100), source))

    def get_snapshots(self, limit=600):
        """Equity history. Live snapshots are thinned to one per hour so a
        long-running bot still returns a readable series."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT timestamp, total_portfolio_value AS value, source FROM performance_metrics "
                "WHERE source = 'replay' OR id IN (SELECT MAX(id) FROM performance_metrics "
                "WHERE source = 'live' GROUP BY substr(timestamp, 1, 13)) "
                "ORDER BY timestamp DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def trade_stats(self):
        """Closed-trade statistics from SELL rows (each SELL closes one position)."""
        with self._connect() as conn:
            r = conn.execute(
                "SELECT COUNT(*) AS n, SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins, "
                "AVG(pnl_pct) AS avg_pct, MAX(pnl_pct) AS best, MIN(pnl_pct) AS worst, "
                "(SELECT COALESCE(SUM(fees), 0) FROM trades) AS fees "
                "FROM trades WHERE trade_type = 'SELL' AND pnl IS NOT NULL").fetchone()
        return dict(r)
