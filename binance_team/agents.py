"""Independent specialists. Each one reads ONLY its own indicators and returns an Opinion;
none of them knows about the others. The LeadAgent is the only place decisions are combined."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    d, c = df.copy(), df["close"]
    d["ema50"] = c.ewm(span=50, adjust=False).mean()
    d["ema200"] = c.ewm(span=200, adjust=False).mean()
    d["px_vs_200"] = c / d["ema200"] - 1
    d["gap"] = d["ema50"] / d["ema200"] - 1
    d["slope200"] = d["ema200"].pct_change(20)
    d["roc20"], d["roc60"] = c.pct_change(20), c.pct_change(60)
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + up / (dn + 1e-12))
    tr = pd.concat([d["high"] - d["low"], (d["high"] - c.shift()).abs(),
                    (d["low"] - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    r = c.pct_change()
    d["vol20"] = r.rolling(20).std()
    d["vol_ratio"] = d["vol20"] / d["vol20"].rolling(100).mean()
    d["vol_x"] = d["volume"] / d["volume"].rolling(20).mean()
    d["dollar_vol"] = (c * d["volume"]).rolling(20).mean()
    return d


@dataclass
class Opinion:
    name: str
    score: float                 # -1 (against) .. +1 (for)
    veto: bool = False           # blocks a NEW entry
    structural: bool = False     # if True and vetoing, an OPEN position should be closed too
    size: float = 1.0            # size multiplier this specialist asks for (0..1)
    reason: str = ""


def _bad(*v):
    return any(x is None or not np.isfinite(x) for x in v)


class TrendAgent:
    name = "trend"

    def opine(self, row, market=None):
        px, gap, slope = row.get("px_vs_200"), row.get("gap"), row.get("slope200")
        if _bad(px, gap, slope):
            return Opinion(self.name, 0, True, False, 0, "not enough history")
        if px < 0 or gap < 0 or slope < 0:
            return Opinion(self.name, -1, True, True, 0, "no uptrend (price/EMA50/EMA200 not aligned)")
        return Opinion(self.name, float(min(1, 0.3 + 5 * px + 5 * gap)), reason="uptrend")


class MomentumAgent:
    name = "momentum"

    def opine(self, row, market=None):
        r20, r60, rsi = row.get("roc20"), row.get("roc60"), row.get("rsi")
        if _bad(r20, r60, rsi):
            return Opinion(self.name, 0, False, False, 1, "no data")
        if rsi > 85:
            return Opinion(self.name, -0.5, True, False, 0, f"overheated RSI {rsi:.0f}")
        return Opinion(self.name, float(np.clip(2 * r20 + 1 * r60, -1, 1)), reason="momentum")


class VolatilityAgent:
    name = "volatility"

    def __init__(self, veto_ratio=2.5, calm_daily_vol=0.04):
        self.veto_ratio, self.calm = veto_ratio, calm_daily_vol

    def opine(self, row, market=None):
        vr, v20 = row.get("vol_ratio"), row.get("vol20")
        if _bad(vr, v20):
            return Opinion(self.name, 0, True, False, 0, "not enough history")
        if vr > self.veto_ratio:
            return Opinion(self.name, -1, True, False, 0, f"volatility spike x{vr:.1f}")
        size = float(np.clip(self.calm / max(v20, 1e-6), 0.25, 1.0))  # wilder market -> smaller position
        return Opinion(self.name, float(np.clip(1 - vr, -1, 1)), size=size, reason=f"size x{size:.2f}")


class VolumeAgent:
    name = "volume"

    def __init__(self, min_dollar_vol=5e6):
        self.min_dv = min_dollar_vol

    def opine(self, row, market=None):
        vx, dv = row.get("vol_x"), row.get("dollar_vol")
        if _bad(vx, dv):
            return Opinion(self.name, 0, True, False, 0, "no volume data")
        if dv < self.min_dv:
            return Opinion(self.name, -1, True, False, 0, "illiquid")
        return Opinion(self.name, float(np.clip(0.2 + 0.5 * (vx - 1), -1, 1)), reason=f"volume x{vx:.1f}")


class MarketAgent:
    """Bitcoin is the market: no long trade unless BTC itself is in an uptrend."""
    name = "market"

    def opine(self, row, market=None):
        if market is None:
            return Opinion(self.name, 0, True, True, 0, "no market data")
        px, slope = market.get("px_vs_200"), market.get("slope200")
        if _bad(px, slope):
            return Opinion(self.name, 0, True, True, 0, "no market data")
        if px < 0 or slope < 0:
            return Opinion(self.name, -1, True, True, 0, "BTC not in uptrend")
        return Opinion(self.name, float(min(1, 0.3 + 5 * px)), reason="BTC confirms")


@dataclass
class LeadConfig:
    threshold: float = 0.30
    weights: dict = field(default_factory=lambda: {
        "trend": 0.30, "momentum": 0.25, "market": 0.25, "volume": 0.10, "volatility": 0.10})


@dataclass
class Decision:
    enter: bool
    hold: bool
    score: float
    size: float
    reason: str


class LeadAgent:
    def __init__(self, cfg: LeadConfig = None):
        self.cfg = cfg or LeadConfig()

    def decide(self, ops):
        vetoes = [o for o in ops if o.veto]
        hold = not any(o.veto and o.structural for o in ops)   # structural veto => leave the position
        if vetoes:
            why = "; ".join(f"{o.name}: {o.reason}" for o in vetoes)
            return Decision(False, hold, 0.0, 0.0, "veto -> " + why)
        w = self.cfg.weights
        score = sum(w[o.name] * o.score for o in ops) / sum(w[o.name] for o in ops)
        if score < self.cfg.threshold:
            return Decision(False, hold, score, 0.0, f"conviction {score:.2f} < {self.cfg.threshold}")
        return Decision(True, hold, score, min(o.size for o in ops), f"conviction {score:.2f}")


def team():
    return [TrendAgent(), MomentumAgent(), VolatilityAgent(), VolumeAgent(), MarketAgent()]


def opinions(row, market_row, agents=None):
    return [a.opine(row, market_row) for a in (agents or team())]
