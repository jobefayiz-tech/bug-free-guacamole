"""Public Binance market data (no account, no API key) plus an offline synthetic generator."""
import numpy as np
import pandas as pd

HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]
MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def _get(path, params):
    import requests
    last = None
    for host in HOSTS:  # api.binance.com is blocked in some countries; the others mirror public data
        try:
            r = requests.get(host + path, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            last = f"{host}: HTTP {r.status_code}"
        except Exception as e:  # network / DNS
            last = f"{host}: {e}"
    raise RuntimeError(f"Could not reach Binance public data ({last})")


def fetch_klines(symbol, interval="1d", bars=2500):
    """Newest `bars` candles for e.g. BTCUSDT, paging backwards 1000 at a time."""
    rows, end = [], None
    while len(rows) < bars:
        params = {"symbol": symbol, "interval": interval, "limit": 1000}
        if end:
            params["endTime"] = end
        chunk = _get("/api/v3/klines", params)
        if not chunk:
            break
        rows = chunk + rows
        end = chunk[0][0] - 1
        if len(chunk) < 1000:
            break
    if not rows:
        raise RuntimeError(f"No candles returned for {symbol}")
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["ts", "open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.pop("ts"), unit="ms")
    df = df.astype(float)
    return df[~df.index.duplicated()].sort_index().tail(bars)


def synthetic(n=2500, seed=0, start=100.0, interval="1d"):
    """Crypto-like fake data (fat tails, bull/bear regimes) for offline tests only."""
    rng = np.random.default_rng(seed)
    drift, left, reg = np.zeros(n), 0, 0.0
    for i in range(n):
        if left == 0:
            reg = rng.choice([-0.004, 0.0, 0.003, 0.005])
            left = int(rng.integers(40, 250))
        drift[i], left = reg, left - 1
    r = drift + rng.standard_t(4, n) * 0.02
    close = start * np.exp(np.cumsum(r))
    open_ = np.concatenate([[start], close[:-1]])
    wick = np.abs(rng.normal(0, 0.01, n))
    high = np.maximum(open_, close) * (1 + wick)
    low = np.minimum(open_, close) * (1 - wick)
    idx = pd.date_range("2018-01-01", periods=n, freq="D" if interval == "1d" else "h")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.uniform(5e3, 2e4, n)}, index=idx)
