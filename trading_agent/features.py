import numpy as np
import pandas as pd

FEATURES = ["r1", "r5", "r10", "r20", "rsi", "ema_ratio", "vol", "atr_pct", "range_pos"]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    c = d["close"]
    d["r1"] = c.pct_change(1)
    d["r5"] = c.pct_change(5)
    d["r10"] = c.pct_change(10)
    d["r20"] = c.pct_change(20)
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = (100 - 100 / (1 + up / (dn + 1e-12))) / 100
    d["ema_ratio"] = c.ewm(span=12, adjust=False).mean() / c.ewm(span=48, adjust=False).mean() - 1
    d["vol"] = d["r1"].rolling(20).std()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - c.shift()).abs(),
                    (d["low"] - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    d["atr_pct"] = d["atr"] / c
    lo, hi = d["low"].rolling(48).min(), d["high"].rolling(48).max()
    d["range_pos"] = (c - lo) / (hi - lo + 1e-12)
    ema200 = c.ewm(span=200, adjust=False).mean()
    d["trend"] = c / ema200 - 1                       # regime: price vs long-term average
    d["trend_slope"] = ema200.pct_change(20)          # regime: is the long-term average rising?
    d["vol_ratio"] = d["vol"] / d["vol"].rolling(200).mean()  # volatility spike detector
    return d


def add_label(d: pd.DataFrame, horizon=12, atr_mult=1.0) -> pd.DataFrame:
    """1 if price rises more than atr_mult*ATR within `horizon` bars (training target only)."""
    d = d.copy()
    fwd_max = d["high"][::-1].rolling(horizon, min_periods=1).max()[::-1].shift(-1)
    d["label"] = ((fwd_max - d["close"]) > atr_mult * d["atr"]).astype(float)
    d.loc[d["high"].shift(-horizon).isna(), "label"] = np.nan
    return d
