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
STATS_URL = "https://api.exchange.coinbase.com/products/{symbol}/stats"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_IDS = {"BTC-USD": "bitcoin", "ETH-USD": "ethereum", "SOL-USD": "solana"}
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


def get_24h_stats(symbol):
    """Last price plus 24-hour open/high/low/volume from Coinbase Exchange.
    Returns None on failure."""
    try:
        r = requests.get(STATS_URL.format(symbol=symbol), headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        last, open_ = float(d["last"]), float(d["open"])
        return {
            "price": last,
            "open_24h": open_,
            "change_24h": last - open_,
            "change_24h_pct": (last / open_ - 1) * 100 if open_ else 0.0,
            "high_24h": float(d["high"]),
            "low_24h": float(d["low"]),
            "volume_24h": float(d["volume"]),
        }
    except Exception as e:
        print(f"[price_fetcher] 24h stats for {symbol} failed: {e}")
        return None


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


def get_coingecko_prices(symbols):
    """Fallback: price and 24h change for several coins in one CoinGecko call."""
    ids = {COINGECKO_IDS[s]: s for s in symbols if s in COINGECKO_IDS}
    if not ids:
        return {}
    try:
        r = requests.get(COINGECKO_URL, headers=HEADERS, timeout=TIMEOUT, params={
            "ids": ",".join(ids), "vs_currencies": "usd", "include_24hr_change": "true"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[price_fetcher] CoinGecko failed: {e}")
        return {}
    out = {}
    for cg_id, sym in ids.items():
        d = data.get(cg_id) or {}
        if "usd" in d:
            change = d.get("usd_24h_change")
            out[sym] = {"price": float(d["usd"]), "change_24h_pct": None if change is None else float(change),
                        "source": "CoinGecko"}
    return out


def get_market_snapshot(symbols=("BTC-USD", "ETH-USD", "SOL-USD")):
    """Live price (+24h change where available) for each symbol.
    Tries Coinbase Exchange, then Coinbase spot, then CoinGecko."""
    out = {}
    for sym in symbols:
        stats = get_24h_stats(sym)
        if stats:
            out[sym] = {**stats, "source": "Coinbase"}
    missing = [s for s in symbols if s not in out]
    for sym in missing:
        spot = get_spot_price(sym)
        if spot:
            out[sym] = {"price": spot, "change_24h_pct": None, "source": "Coinbase"}
    need_change = [s for s in symbols if s not in out or out[s].get("change_24h_pct") is None]
    if need_change:
        for sym, d in get_coingecko_prices(need_change).items():
            if sym not in out:
                out[sym] = d
            else:
                out[sym]["change_24h_pct"] = d["change_24h_pct"]
    return out
