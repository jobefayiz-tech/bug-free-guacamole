import numpy as np
import pandas as pd

from .features import FEATURES, add_features, add_label
from .model import LogisticModel
from .risk import Position, RiskConfig, RiskManager

HORIZON = 12


def run_backtest(df, cfg: RiskConfig = None, cash=10_000.0, warmup=500,
                 train_window=1500, retrain_every=200):
    """Walk-forward backtest: the model only sees data prior to each decision;
    signals fill at the next bar's open."""
    cfg = cfg or RiskConfig()
    d = add_label(add_features(df), HORIZON)
    X = d[FEATURES].to_numpy()
    y = d["label"].to_numpy()
    o, h, l, c, atr = (d[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
    rm, model, pos, pending = RiskManager(cfg, cash), None, None, False
    trades, equity_curve = [], []
    for i in range(warmup, len(d)):
        if (i - warmup) % retrain_every == 0:
            lo, hi = max(60, i - train_window), i - HORIZON
            ok = ~np.isnan(X[lo:hi]).any(1) & ~np.isnan(y[lo:hi])
            model = LogisticModel().fit(X[lo:hi][ok], y[lo:hi][ok])
        if pending and pos is None:
            px = o[i] * (1 + cfg.slippage)
            qty = rm.size(cash, px, atr[i - 1])
            if qty > 0 and qty * px <= cash:
                cash -= qty * px * (1 + cfg.fee_rate)
                pos = Position(px, qty, atr[i - 1], cfg)
        pending = False
        if pos:
            ex = pos.check_exit(o[i], h[i], l[i])
            if ex is not None:
                ex *= 1 - cfg.slippage
                cash += pos.qty * ex * (1 - cfg.fee_rate)
                trades.append(pos.qty * (ex - pos.entry) - cfg.fee_rate * pos.qty * (ex + pos.entry))
                pos = None
            else:
                pos.update(h[i])
        eq = cash + (pos.qty * c[i] if pos else 0)
        rm.on_equity(d.index[i], eq)
        equity_curve.append(eq)
        if pos is None and rm.can_trade(eq) and not np.isnan(X[i]).any():
            pending = model.predict_proba(X[i:i + 1])[0] >= cfg.entry_threshold
    eq = pd.Series(equity_curve, index=d.index[warmup:])
    t = np.array(trades)
    dd = (eq / eq.cummax() - 1).min()
    return {
        "trades": len(t),
        "win_rate": float((t > 0).mean()) if len(t) else 0.0,
        "total_return": float(eq.iloc[-1] / eq.iloc[0] - 1),
        "max_drawdown": float(dd),
        "worst_trade": float(t.min()) if len(t) else 0.0,
        "buy_and_hold": float(c[-1] / c[warmup] - 1),  # benchmark: just hold the asset
        "final_equity": float(eq.iloc[-1]),
    }
