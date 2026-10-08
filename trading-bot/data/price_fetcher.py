"""
data/price_fetcher.py

Market data from Coinbase's public APIs (no API key needed):
  - spot prices:   https://api.coinbase.com/v2/prices/{symbol}/spot
  - daily candles: https://api.exchange.coinbase.com/products/{symbol}/candles
"""

import time

import pandas as pd
import requests

SPOT_URL = "https://api.coinbase.com/v2/prices/{symbol}/spot"
CANDLES_URL = "https://api.exchange.coinbase.com/products/{symbol}/candles"
HEADERS = {"User-Agent": "chainproof-paper-bot/1.0"}
TIMEOUT = 10


def get_spot_price(symbol):
    """Latest spot price as a float, or None if Coinbase can't be reached."""
    try:
        r = requests.get(SPOT_URL.format(symbol=symbol), headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return float(r.json()["data"]["amount"])
    except Exception as e:  # network errors, bad JSON, rate limits
        print(f"[price_fetcher] spot price for {symbol} failed: {e}")
        return None


def get_all_prices(symbols=("BTC-USD", "ETH-USD", "SOL-USD")):
    return {s: get_spot_price(s) for s in symbols}


def get_daily_candles(symbol, days=300):
    """Up to 300 daily OHLCV candles, oldest first, lowercase columns.
    Returns an empty DataFrame on failure."""
    end = int(time.time())
    start = end - days * 86400
    params = {
        "granularity": 86400,
        "start": pd.Timestamp(start, unit="s").isoformat(),
        "end": pd.Timestamp(end, unit="s").isoformat(),
    }
    try:
        r = requests.get(CANDLES_URL.format(symbol=symbol), params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json()  # [[time, low, high, open, close, volume], ...] newest first
    except Exception as e:
        print(f"[price_fetcher] candles for {symbol} failed: {e}")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)
