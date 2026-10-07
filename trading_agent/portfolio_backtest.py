import numpy as np
import pandas as pd

from .backtest import HORIZON
from .features import FEATURES, add_features, add_label
from .model import LogisticModel
from .risk import Portfolio, Position, RiskConfig


def run_portfolio_backtest(dfs, cfg: RiskConfig = None, cash=10_000.0, warmup=500,
                           train_window=1500, retrain_every=200):
    """Walk-forward backtest of many symbols sharing ONE cash pool and the account-wide
    limits (max positions, total risk, total exposure, daily-loss, drawdown kill switch).
    Signals fill at the next bar's open; when several symbols signal at once, the highest
    model probability gets the budget first."""
    cfg = cfg or RiskConfig()
    idx = None
    for df in dfs.values():
        idx = df.index if idx is None else idx.intersection(df.index)
    syms = list(dfs)
    if len(idx) < warmup + 100:
        raise ValueError(f"Only {len(idx)} bars are shared by all symbols; need at least "
                         f"{warmup + 100}. Per-symbol bars: "
                         + ", ".join(f"{s}={len(d)}" for s, d in dfs.items()))
    D = {s: add_label(add_features(dfs[s].loc[idx]), HORIZON) for s in syms}
    A = {s: {k: D[s][k].to_numpy() for k in ("open", "high", "low", "close", "atr", "label")}
         for s in syms}
    X = {s: D[s][FEATURES].to_numpy() for s in syms}
    n = len(idx)
    pf, models, pending = Portfolio(cfg), {}, {}
    stats = dict(blocked=0, max_open=0, exposure_sum=0.0)
    trades = {s: [] for s in syms}
    curve = []
    cash0 = cash

    def close_pos(s, px):
        nonlocal cash
        pos = pf.positions.pop(s)
        px *= 1 - cfg.slippage
        cash += pos.qty * px * (1 - cfg.fee_rate)
        trades[s].append(pos.qty * (px - pos.entry) - cfg.fee_rate * pos.qty * (px + pos.entry))

    def manage(s, i):
        pos = pf.positions[s]
        a = A[s]
        ex = pos.check_exit(a["open"][i], a["high"][i], a["low"][i])
        if ex is not None:
            close_pos(s, ex)
        else:
            pos.update(a["high"][i])

    for i in range(warmup, n):
        if (i - warmup) % retrain_every == 0:
            for s in syms:
                lo, hi = max(60, i - train_window), i - HORIZON
                ok = ~np.isnan(X[s][lo:hi]).any(1) & ~np.isnan(A[s]["label"][lo:hi])
                models[s] = (LogisticModel().fit(X[s][lo:hi][ok], A[s]["label"][lo:hi][ok])
                             if ok.sum() >= 100 else None)
        if pf.rm is None:
            pf.start(idx[i], cash)
        # 1) positions held from earlier bars: stops / targets / trailing
        for s in list(pf.positions):
            manage(s, i)
        # 2) new entries at this bar's open, best signal first
        for s, _p in sorted(pending.items(), key=lambda kv: -kv[1]):
            if s in pf.positions:
                continue
            eq = cash + sum(p.qty * A[t]["close"][i - 1] for t, p in pf.positions.items())
            px = A[s]["open"][i] * (1 + cfg.slippage)
            atr = A[s]["atr"][i - 1]
            qty = pf.rm.size(eq, px, atr)
            qty = pf.cap_qty(s, qty, px, px - cfg.stop_atr * atr, eq, cash)
            if qty <= 0:
                stats["blocked"] += 1
                continue
            cash -= qty * px * (1 + cfg.fee_rate)
            pf.positions[s] = Position(px, qty, atr, cfg)
            manage(s, i)  # the entry bar itself can hit the stop
        pending = {}
        eq = cash + sum(p.qty * A[t]["close"][i] for t, p in pf.positions.items())
        pf.rm.on_equity(idx[i], eq)
        curve.append(eq)
        stats["max_open"] = max(stats["max_open"], len(pf.positions))
        stats["exposure_sum"] += sum(p.qty * A[t]["close"][i] for t, p in pf.positions.items()) / eq
        # 3) signals for the next bar
        if pf.rm.can_trade(eq):
            for s in syms:
                if s not in pf.positions and models[s] and not np.isnan(X[s][i]).any():
                    p = models[s].predict_proba(X[s][i:i + 1])[0]
                    if p >= cfg.entry_threshold:
                        pending[s] = p

    eq = pd.Series(curve, index=idx[warmup:])
    allt = np.concatenate([np.array(t) for t in trades.values()]) if any(trades.values()) else np.array([])
    bh = np.mean([A[s]["close"][-1] / A[s]["close"][warmup] - 1 for s in syms])
    return {
        "symbols": len(syms),
        "trades": len(allt),
        "win_rate": float((allt > 0).mean()) if len(allt) else 0.0,
        "total_return": float(eq.iloc[-1] / cash0 - 1),
        "max_drawdown": float((eq / eq.cummax() - 1).min()),
        "equal_weight_buy_and_hold": float(bh),
        "max_open_positions": stats["max_open"],
        "avg_exposure": stats["exposure_sum"] / len(eq),
        "entries_blocked": stats["blocked"],
        "pnl_by_symbol": {s: round(float(sum(t)), 2) for s, t in trades.items()},
        "final_equity": float(eq.iloc[-1]),
    }
