#!/usr/bin/env python3
"""
export_price_fixture.py -- writes the price series the replay ran on to
fixtures/, so the strategy can be re-run from a clean clone

Run once, on the machine that has the bot's database:
    python export_price_fixture.py                       # BTC-USD
    python export_price_fixture.py --symbols BTC-USD ETH-USD SOL-USD

It prefers the bot's own loader (TradingDatabase.get_price_data), because
that is exactly what generate_replay_data.py used, and falls back to
reading the price_history table directly. Then commit the CSVs in
fixtures/ and run replay_check.py to confirm they reproduce the published
decisions.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(HERE, "..", "trading-bot")
sys.path.append(BOT_DIR)

from price_data import COLUMNS, load_prices_db  # noqa: E402

FIXTURE_DIR = os.path.join(HERE, "fixtures")
DEFAULT_DB = os.path.join(BOT_DIR, "data", "trading_bot.db")


def load(symbol, db_path):
    try:
        from data.database import TradingDatabase
        df = TradingDatabase().get_price_data(symbol)
        source = "TradingDatabase.get_price_data"
    except ImportError:
        df = load_prices_db(db_path, symbol)
        source = f"price_history table in {db_path}"
    return df, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="*", default=["BTC-USD"])
    parser.add_argument("--db", default=DEFAULT_DB, help="used only if TradingDatabase is unavailable")
    args = parser.parse_args()

    os.makedirs(FIXTURE_DIR, exist_ok=True)
    for symbol in args.symbols:
        df, source = load(symbol, args.db)
        if df.empty:
            print(f"{symbol}: no data, skipped")
            continue
        path = os.path.join(FIXTURE_DIR, f"{symbol}.csv")
        df[COLUMNS].to_csv(path, index_label="timestamp")
        print(f"{symbol}: {len(df)} rows, {df.index[0]} to {df.index[-1]} "
              f"(from {source}) -> {os.path.relpath(path, HERE)}")


if __name__ == "__main__":
    main()
