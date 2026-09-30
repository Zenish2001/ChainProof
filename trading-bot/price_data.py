"""
price_data.py -- load daily OHLCV prices from the bot's database or a CSV

Both loaders return the shape the strategy code expects: a DataFrame
indexed by a UTC timestamp, sorted oldest first, with float columns
open, high, low, close and volume.
"""

import sqlite3

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


def _normalise(df):
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "timestamp"
    df = df.sort_index()

    duplicates = df.index.duplicated(keep="first")
    if duplicates.any():
        print(f"WARNING: dropped {duplicates.sum()} duplicate timestamps "
              f"(kept the first row for each)")
        df = df[~duplicates]

    return df[COLUMNS].astype(float)


def list_symbols(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT symbol FROM price_history ORDER BY symbol").fetchall()
    return [r[0] for r in rows]


def load_prices_db(db_path, symbol):
    """Read one symbol from the price_history table of the bot's SQLite db."""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT timestamp, open, high, low, close, volume FROM price_history "
            "WHERE symbol = ? ORDER BY timestamp",
            conn,
            params=(symbol,),
            index_col="timestamp",
        )
    if df.empty:
        raise ValueError(f"No rows for {symbol} in {db_path}")
    return _normalise(df)


def load_prices_csv(path):
    """Read a price fixture written by export_price_fixture.py."""
    df = pd.read_csv(path, index_col="timestamp")
    return _normalise(df)
