"""Deterministic synthetic OHLCV data for tests. Never used for results."""

import numpy as np
import pandas as pd


def synthetic_prices(days=500, seed=7, start_price=40000.0):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0008, 0.03, days)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, 0.01, days))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.uniform(1e9, 5e9, days)
    index = pd.date_range("2024-01-01", periods=days, freq="D", tz="UTC", name="timestamp")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
