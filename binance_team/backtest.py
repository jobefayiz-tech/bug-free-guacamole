import numpy as np
import pandas as pd

from .agents import LeadAgent, LeadConfig, build_features, opinions


def stats(r, per=365):
    r = pd.Series(r).dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / per
    tot = float(eq.iloc[-1] - 1)
    return {"total_return": tot,
            "cagr": float((1 + tot) ** (1 / yrs) - 1) if yrs > 0 and tot > -1 else -1.0,
            "sharpe": float(r.mean() / r.std() * np.sqrt(per)) if r.std() > 0 else 0.0,
            "max_drawdown": float((eq / eq.cummax() - 1).min())}


def run_backtest(dfs, market="BTCUSDT", cash=20.0, fee=0.001, slip=0.0005, risk=0.02,
                 max_pos_frac=0.5, min_notional=5.0, stop_atr=2.5, trail_atr=3.0,
                 lock_start_atr=2.0, lock_frac=0.4, halt_drawdown=None, warmup=260,
                 lead_threshold=None, max_positions=5, rank="conviction"):
    """Long-only spot portfolio sharing one cash pool. Decisions use data up to a bar's close;
    orders fill at the NEXT bar's open (no look-ahead)."""
    syms = list(dfs)
    idx = None
    for d in dfs.values():
        idx = d.index if idx is None else idx.intersection(d.index)
    if len(idx) < warmup + 200:
        raise ValueError(f"Only {len(idx)} shared bars; need {warmup + 200}.")
    F = {s: build_features(dfs[s].loc[idx]) for s in syms}
    A = {s: {k: F[s][k].to_numpy() for k in ("open", "high", "low", "close", "atr")} for s in syms}
    cols = ["px_vs_200", "gap", "slope200", "roc20", "roc60", "rsi", "vol20", "vol_ratio",
            "vol_x", "dollar_vol"]
    R = {s: {k: F[s][k].to_numpy() for k in cols} for s in syms}
    lead = LeadAgent(LeadConfig(threshold=lead_threshold) if lead_threshold else None)
    pos, cash0, peak = {}, cash, cash
    pend_entry, pend_exit = {}, set()
    eqs, trades, vetoes, small, exposure, max_open = [], [], {}, 0, [], 0

    def row(s, i):
        return {k: v[i] for k, v in R[s].items()}

    def close_pos(s, px):
        nonlocal cash
        p = pos.pop(s)
        px *= 1 - slip
        cash += p["qty"] * px * (1 - fee)
        trades.append((s, p["qty"] * (px - p["entry"]) - fee * p["qty"] * (px + p["entry"]),
                       p["qty"] * p["entry"]))

    for i in range(warmup, len(idx)):
        for s in list(pend_exit):                       # a) exits decided at yesterday's close
            if s in pos:
                close_pos(s, A[s]["open"][i])
        pend_exit.clear()
        for s, (mult, atr, _sc) in sorted(pend_entry.items(), key=lambda kv: -kv[1][2]):  # b) best conviction first
            if len(pos) >= max_positions:
                break
            px = A[s]["open"][i] * (1 + slip)
            eq = cash + sum(p["qty"] * A[t]["open"][i] for t, p in pos.items())
            dist = stop_atr * atr
            qty = min(eq * risk / dist * mult, eq * max_pos_frac / px, cash / (px * (1 + fee)))
            if qty * px < min_notional:
                small += 1
                continue
            cash -= qty * px * (1 + fee)
            pos[s] = dict(qty=qty, entry=px, stop=px - dist, high=px, atr=atr)
        pend_entry.clear()
        for s in list(pos):                              # c) stops & trailing on this bar
            p, a = pos[s], A[s]
            if a["low"][i] <= p["stop"]:
                close_pos(s, min(p["stop"], a["open"][i]))
                continue
            p["high"] = max(p["high"], a["high"][i])
            gain = p["high"] - p["entry"]
            p["stop"] = max(p["stop"], p["high"] - trail_atr * p["atr"])
            if gain >= lock_start_atr * p["atr"]:
                p["stop"] = max(p["stop"], p["entry"] + lock_frac * gain)
        eq = cash + sum(p["qty"] * A[s]["close"][i] for s, p in pos.items())
        eqs.append(eq)
        exposure.append(1 - cash / eq if eq > 0 else 0)
        max_open = max(max_open, len(pos))
        peak = max(peak, eq)
        halted = halt_drawdown is not None and eq < peak * (1 - halt_drawdown)
        mrow = row(market, i) if market in R else None
        for s in syms:                                   # d) team decides at the close
            dec = lead.decide(opinions(row(s, i), mrow))
            if s in pos:
                if not dec.hold:
                    pend_exit.add(s)
            elif dec.enter and not halted:
                key = dec.score if rank == "conviction" else dec.score * A[s]["close"][i] / (stop_atr * A[s]["atr"][i])
                pend_entry[s] = (dec.size, A[s]["atr"][i], key)
            elif not dec.enter and dec.reason.startswith("veto"):
                name = dec.reason.split("->")[1].split(":")[0].strip()
                vetoes[name] = vetoes.get(name, 0) + 1

    ix = idx[warmup:]
    eq = pd.Series(eqs, index=ix)
    strat = eq.pct_change().fillna(eq.iloc[0] / cash0 - 1)
    bench_s = market if market in dfs else syms[0]
    bench = F[bench_s]["close"].loc[ix].pct_change().fillna(0)
    equal = pd.concat([F[s]["close"].loc[ix].pct_change().fillna(0) for s in syms], axis=1).mean(axis=1)
    pnl = np.array([t[1] for t in trades])
    yearly = {int(y): {"team": float((1 + strat[g.index]).prod() - 1),
                       bench_s: float((1 + bench[g.index]).prod() - 1)}
              for y, g in strat.groupby(ix.year)}
    return {"period": f"{ix[0]:%Y-%m-%d} -> {ix[-1]:%Y-%m-%d}", "start_cash": cash0,
            "final_cash": float(eq.iloc[-1]), "team": stats(strat),
            f"{bench_s} buy&hold": stats(bench), "equal-weight buy&hold": stats(equal),
            "trades": len(pnl), "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0,
            "avg_exposure": float(np.mean(exposure)), "max_open": max_open, "orders_too_small": small,
            "vetoes": vetoes, "yearly": yearly, "bench": bench_s,
            "pnl_by_symbol": {s: round(float(sum(t[1] for t in trades if t[0] == s)), 4) for s in syms}}
