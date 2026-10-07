"""A team of specialist agents supervised by a lead agent.

Each specialist looks at ONE aspect of the market and returns an Opinion
(score in [-1, 1], optionally a veto). The LeadAgent combines them: any veto blocks
the trade, otherwise a weighted score must clear a threshold, and the score sets
the position size. The lead also learns: specialists that keep backing losing trades
lose weight, those backing winners gain weight.
"""
from dataclasses import dataclass, field

import numpy as np

from .features import FEATURES
from .model import LogisticModel


@dataclass
class TeamConfig:
    lead_threshold: float = 0.25      # min weighted score to enter
    veto_vol_ratio: float = 2.0       # volatility this many times normal = panic, stay out
    size_floor: float = 0.5           # smallest fraction of the normal position size
    weights: dict = field(default_factory=lambda: {
        "ml": 0.40, "momentum": 0.20, "regime": 0.25, "volatility": 0.15})


@dataclass
class Opinion:
    name: str
    score: float
    veto: bool = False
    reason: str = ""


@dataclass
class Decision:
    enter: bool
    score: float
    size_mult: float
    reason: str


def _bad(*vals):
    return any(v is None or not np.isfinite(v) for v in vals)


class RegimeAgent:
    """Market-regime specialist: only allow longs in an established uptrend."""
    name = "regime"

    def opine(self, row):
        t, slope = row.get("trend"), row.get("trend_slope")
        if _bad(t, slope):
            return Opinion(self.name, 0.0, True, "not enough history")
        if t < 0 or slope < 0:
            return Opinion(self.name, -1.0, True, "downtrend (price or long average falling)")
        return Opinion(self.name, float(min(1.0, 0.2 + 15 * t)), False, "uptrend")


class VolatilityAgent:
    """Risk-climate specialist: stand aside when volatility explodes."""
    name = "volatility"

    def __init__(self, cfg: TeamConfig):
        self.cfg = cfg

    def opine(self, row):
        vr = row.get("vol_ratio")
        if _bad(vr):
            return Opinion(self.name, 0.0, True, "not enough history")
        if vr > self.cfg.veto_vol_ratio:
            return Opinion(self.name, -1.0, True, f"volatility spike x{vr:.1f}")
        return Opinion(self.name, float(np.clip(1.0 - vr, -1, 1)), False, "calm" if vr < 1 else "normal")


class MomentumAgent:
    """Momentum specialist: recent strength and short/long average cross."""
    name = "momentum"

    def opine(self, row):
        r20, ema = row.get("r20"), row.get("ema_ratio")
        if _bad(r20, ema):
            return Opinion(self.name, 0.0, False, "no data")
        return Opinion(self.name, float(np.clip(8 * r20 + 15 * ema, -1, 1)), False, "momentum")


class MLAgent:
    """Prediction specialist: learned probability that price rises more than 1 ATR soon."""
    name = "ml"

    def __init__(self):
        self.model = None

    def fit_arrays(self, X, y):
        self.model = LogisticModel().fit(X, y)

    def prob(self, row):
        x = np.array([[row.get(f, np.nan) for f in FEATURES]], float)
        if self.model is None or not np.isfinite(x).all():
            return None
        return float(self.model.predict_proba(x)[0])

    def opine(self, row):
        p = self.prob(row)
        if p is None:
            return Opinion(self.name, 0.0, False, "no model")
        return Opinion(self.name, float(np.clip((p - 0.5) * 5, -1, 1)), False, f"p={p:.2f}")


class Team:
    """The specialists that follow ONE symbol."""

    def __init__(self, cfg: TeamConfig = None):
        self.cfg = cfg or TeamConfig()
        self.ml = MLAgent()
        self.members = [self.ml, MomentumAgent(), RegimeAgent(), VolatilityAgent(self.cfg)]

    def opinions(self, row):
        return [m.opine(row) for m in self.members]


class LeadAgent:
    """Supervisor: weighs the specialists, applies vetoes and account limits, sizes the trade."""

    def __init__(self, cfg: TeamConfig = None):
        self.cfg = cfg or TeamConfig()
        self.base = dict(self.cfg.weights)
        self.w = dict(self.base)

    def decide(self, opinions, account_ok=True):
        if not account_ok:
            return Decision(False, 0.0, 0.0, "risk officer: account loss limits reached")
        vetoes = [o for o in opinions if o.veto]
        if vetoes:
            return Decision(False, 0.0, 0.0, "veto: " + "; ".join(f"{o.name} ({o.reason})" for o in vetoes))
        tw = sum(self.w[o.name] for o in opinions)
        score = sum(self.w[o.name] * o.score for o in opinions) / tw
        if score < self.cfg.lead_threshold:
            return Decision(False, score, 0.0, f"conviction {score:.2f} below {self.cfg.lead_threshold}")
        mult = float(np.clip(0.5 + score, self.cfg.size_floor, 1.0))
        return Decision(True, score, mult, f"conviction {score:.2f}")

    def learn(self, scores, pnl):
        """scores: {specialist: score at entry}. Reward backers of winners, penalise backers of losers."""
        for name, sc in scores.items():
            if sc > 0.1 and name in self.w:
                factor = 1.1 if pnl > 0 else 0.9
                self.w[name] = float(np.clip(self.w[name] * factor,
                                             0.25 * self.base[name], 2 * self.base[name]))
