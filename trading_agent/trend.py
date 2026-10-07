"""Slow, low-turnover trend portfolio on DAILY bars, always compared with buy-and-hold.

Rules (all decided at a day's close, applied from the next day, so no look-ahead):
  * an asset is "on" only while its price is above its 200-day average;
  * "on" assets share the portfolio by inverse volatility (calmer assets get more);
  * total exposure is scaled down so estimated portfolio volatility stays <= target;
  * whatever is not invested stays in cash (earning `cash_rate`);
  * rebalance about once a month; costs are charged on every change in weights.
"""
import numpy as np
import pandas as pd


def _stats(r, periods=252):
    r = pd.Series(r).dropna()
    eq = (1 + r).cumprod()
    total = float(eq.iloc[-1] - 1)
    years = len(r) / periods
    sd = float(r.std() * np.sqrt(periods))
    return {
        "total_return": total,
        "cagr": float((1 + total) ** (1 / years) - 1) if years > 0 else 0.0,
        "volatility": sd,
        "sharpe": float(r.mean() / r.std() * np.sqrt(periods)) if r.std() > 0 else 0.0,
        "max_drawdown": float((eq / eq.cummax() - 1).min()),
    }


def run_trend_backtest(dfs, benchmark, target_vol=0.10, sma=200, rebalance=21,
                       vol_win=60, cost=0.0015, cash_rate=0.0):
    px = pd.DataFrame({s: d["close"] for s, d in dfs.items()}).dropna()
    if len(px) < sma + 250:
        raise ValueError(f"Need at least {sma + 250} daily bars, got {len(px)}")
    rets = px.pct_change().fillna(0.0)
    r = rets.to_numpy()
    on = (px > px.rolling(sma).mean()).to_numpy()
    cols = list(px.columns)
    bench_col = cols.index(benchmark)
    n, k = r.shape
    cur, pending, port = np.zeros(k), 0.0, np.zeros(n)
    for t in range(1, n):
        port[t] = cur @ r[t] + (1 - cur.sum()) * cash_rate / 252 - pending
        pending = 0.0
        if t >= sma and (t - sma) % rebalance == 0:
            sel = on[t]
            target = np.zeros(k)
            if sel.any():
                win = rets.iloc[t - vol_win + 1:t + 1]
                vol = win.std().to_numpy() * np.sqrt(252)
                w = np.where(sel, 1 / np.maximum(vol, 1e-6), 0.0)
                w /= w.sum()
                cov = win.cov().to_numpy() * 252
                pv = float(np.sqrt(max(w @ cov @ w, 1e-12)))
                target = w * min(1.0, target_vol / pv)
            pending = float(np.abs(target - cur).sum() * cost)
            cur = target
    idx = px.index[sma:]
    strat = pd.Series(port[sma:], index=idx)
    bench = pd.Series(r[sma:, bench_col], index=idx)
    equal = pd.Series(r[sma:].mean(axis=1), index=idx)
    yearly = {}
    for y, g in strat.groupby(idx.year):
        yearly[int(y)] = {
            "strategy": float((1 + g).prod() - 1),
            benchmark: float((1 + bench[g.index]).prod() - 1),
        }
    return {
        "period": f"{idx[0]:%Y-%m-%d} -> {idx[-1]:%Y-%m-%d}",
        "strategy": _stats(strat),
        f"{benchmark} buy&hold": _stats(bench),
        "equal-weight buy&hold": _stats(equal),
        "yearly": yearly,
        "allocation_now": {c: round(float(w), 3) for c, w in zip(cols, cur) if w > 0},
        "cash_now": round(float(1 - cur.sum()), 3),
    }
