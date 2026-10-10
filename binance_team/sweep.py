"""Robustness check: run the SAME team under many reasonable settings and look at the whole
spread, instead of trusting one hand-picked result (which is how people fool themselves)."""
import itertools

import numpy as np

from .backtest import run_backtest

GRID = dict(risk=[0.01, 0.02, 0.04], lead_threshold=[0.2, 0.3, 0.4], stop_atr=[2.0, 2.5, 3.5],
            rank=["conviction", "per_risk"])


def run_sweep(dfs, cash=1000.0, grid=None):
    grid = grid or GRID
    keys = list(grid)
    rows = []
    for combo in itertools.product(*grid.values()):
        kw = dict(zip(keys, combo))
        r = run_backtest(dfs, cash=cash, **kw)
        rows.append({**kw, "total": r["team"]["total_return"], "dd": r["team"]["max_drawdown"],
                     "sharpe": r["team"]["sharpe"], "trades": r["trades"],
                     "exposure": r["avg_exposure"]})
    bench = r[f"{r['bench']} buy&hold"]
    tot, dd, sh = (np.array([x[k] for x in rows]) for k in ("total", "dd", "sharpe"))
    by_rank = {}
    for rk in sorted({x.get("rank", "conviction") for x in rows}):
        sub = [x for x in rows if x.get("rank", "conviction") == rk]
        by_rank[rk] = {"n": len(sub), "total_median": float(np.median([x["total"] for x in sub])),
                       "dd_median": float(np.median([x["dd"] for x in sub])),
                       "sharpe_median": float(np.median([x["sharpe"] for x in sub])),
                       "share_beating_bench_sharpe": float(np.mean([x["sharpe"] > bench["sharpe"] for x in sub]))}
    summary = {"by_rank": by_rank,
        "configs": len(rows), "bench": r["bench"], "bench_total": bench["total_return"],
        "bench_dd": bench["max_drawdown"], "bench_sharpe": bench["sharpe"],
        "total_min": tot.min(), "total_median": float(np.median(tot)), "total_max": tot.max(),
        "dd_worst": dd.min(), "dd_median": float(np.median(dd)),
        "sharpe_median": float(np.median(sh)),
        "share_less_drawdown_than_bench": float((dd > bench["max_drawdown"]).mean()),
        "share_beating_bench_return": float((tot > bench["total_return"]).mean()),
        "share_beating_bench_sharpe": float((sh > bench["sharpe"]).mean()),
        "share_positive": float((tot > 0).mean()),
    }
    return rows, summary
