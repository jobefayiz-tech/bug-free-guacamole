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


ALPACA_TF = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour", "1d": "1Day"}


def _alpaca_headers():
    import os
    return {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
            "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET"]}


def fetch_alpaca_bars(_exchange_id, symbol, timeframe="1h", limit=1000):
    """US stock candles from Alpaca (free IEX feed)."""
    import requests
    start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=365 if timeframe == "1d" else 120))
    r = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
        params={"timeframe": ALPACA_TF[timeframe], "limit": 10000, "feed": "iex",
                "adjustment": "split", "start": start.isoformat()},
        headers=_alpaca_headers(), timeout=20)
    r.raise_for_status()
    rows = r.json().get("bars") or []
    df = pd.DataFrame(rows).rename(columns={"o": "open", "h": "high", "l": "low",
                                            "c": "close", "v": "volume", "t": "ts"})
    df.index = pd.to_datetime(df.pop("ts"))
    return df[["open", "high", "low", "close", "volume"]].tail(limit)


def fetch_any(exchange_id, symbol, timeframe="1h", limit=1000):
    """Route to Alpaca for stocks (exchange 'alpaca'), otherwise to ccxt."""
    if exchange_id == "alpaca":
        return fetch_alpaca_bars(exchange_id, symbol, timeframe, limit)
    return fetch_ohlcv(exchange_id, symbol, timeframe, limit)
