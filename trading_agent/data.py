import numpy as np
import pandas as pd


def synthetic_ohlcv(n=4000, seed=0, start_price=100.0, freq="1h"):
    """Regime-switching random walk, for offline testing only."""
    rng = np.random.default_rng(seed)
    drift = np.zeros(n)
    regime, left = 0.0, 0
    for i in range(n):
        if left == 0:
            regime = rng.choice([-0.0004, 0.0, 0.0006])
            left = int(rng.integers(50, 300))
        drift[i] = regime
        left -= 1
    rets = drift + rng.normal(0, 0.006, n)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    idx = pd.date_range("2024-01-01", periods=n, freq=freq)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": rng.uniform(100, 1000, n)}, index=idx)


def fetch_ohlcv(exchange_id, symbol, timeframe="1h", limit=1000):
    """Fetch candles from any exchange supported by ccxt (binance, kraken, bybit, ...)."""
    import ccxt
    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df.pop("ts"), unit="ms")
    return df
