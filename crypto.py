"""Binance team CLI (paper trading only).
  python crypto.py backtest [--cash 20] [--synthetic]
  python crypto.py sweep             same team under 54 settings (27 x 2 rankings): is the result stable or a fluke?
  python crypto.py scan --top 25     rank the most liquid coins by what the team would enter today
  python crypto.py status            today's decision of every specialist for every coin
  python crypto.py paper [--loop 3600]
  python crypto.py report            paper result vs just holding BTC
"""
import argparse
import time

from binance_team.agents import LeadAgent, build_features, opinions
from binance_team.backtest import run_backtest
from binance_team.data import fetch_klines, synthetic, top_symbols
from binance_team.scan import scan
from binance_team.paper import PaperTrader
from binance_team.sweep import run_sweep

DEFAULT = ("BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,LINKUSDT,LTCUSDT")


def pct(x):
    return f"{x:>8.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backtest", "sweep", "scan", "status", "paper", "report"])
    ap.add_argument("--symbols", default=DEFAULT)
    ap.add_argument("--cash", type=float, default=None, help="backtest default 20; paper default 1000 (fake money)")
    ap.add_argument("--bars", type=int, default=2500)
    ap.add_argument("--top", type=int, default=0, help="scan/paper: use the N most liquid USDT coins right now")
    ap.add_argument("--rank", choices=["conviction", "per_risk"], default="conviction",
                    help="order of entries when slots are limited: raw conviction, or conviction per unit of risk")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--loop", type=int, default=0, help="paper: repeat every N seconds")
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",")]

    if a.mode == "scan":
        syms = top_symbols(a.top or 25)
        rows = scan(syms, rank=a.rank)
        buy = [r for r in rows if r["enter"]]
        print(f"Scanned {len(rows)} liquid coins. BTC is the market gauge. (Ranking by the team's rules, NOT a prediction.)\n")
        print("COINS THE TEAM WOULD ENTER TODAY:" if buy else "NO COIN PASSES THE TEAM'S RULES TODAY. Staying out is a valid result.")
        if buy:
            print(f"{'coin':10s}{'conviction':>11s}{'conv/risk':>10s}{'size':>6s}{'price':>12s}{'stop':>12s}{'risk/coin':>10s}{'30d':>8s}{'90d':>8s}")
            for r in buy:
                print(f"{r['symbol']:10s}{r['score']:>11.2f}{r['per_risk']:>10.1f}{r['size']:>6.2f}{r['price']:>12.4f}{r['stop']:>12.4f}"
                      f"{r['risk_pct']:>10.1%}{r['r30']:>8.0%}{r['r90']:>8.0%}")
        print("\nREJECTED (reason):")
        for r in [r for r in rows if not r["enter"]]:
            print(f"  {r['symbol']:10s}{r['reason']}")
        return

    if a.mode == "sweep":
        dfs = {s: (synthetic(a.bars, seed=i) if a.synthetic else fetch_klines(s, "1d", a.bars))
               for i, s in enumerate(syms)}
        rows, m = run_sweep(dfs, cash=a.cash or 1000.0)
        print(f"{m['configs']} setting combinations (risk, threshold, stop, ranking) tested on the same data\n")
        print(f"{'risk':>6s}{'thresh':>8s}{'stopATR':>9s}{'ranking':>12s}{'total':>9s}{'maxDD':>9s}{'Sharpe':>8s}{'trades':>8s}")
        for x in sorted(rows, key=lambda x: -x["sharpe"]):
            print(f"{x['risk']:>6.0%}{x['lead_threshold']:>8.1f}{x['stop_atr']:>9.1f}{x['rank']:>12s}"
                  f"{x['total']:>9.1%}{x['dd']:>9.1%}{x['sharpe']:>8.2f}{x['trades']:>8d}")
        print("\nBy ranking method (median over its settings):")
        for rk, v in m["by_rank"].items():
            print(f"  {rk:11s} total {v['total_median']:>7.1%} | max DD {v['dd_median']:>7.1%} | Sharpe {v['sharpe_median']:.2f}"
                  f" | beats {m['bench']} on Sharpe in {v['share_beating_bench_sharpe']:.0%} of its settings")
        b = m["bench"]
        print(f"\n{b} buy&hold: total {m['bench_total']:.1%}, max drawdown {m['bench_dd']:.1%}, Sharpe {m['bench_sharpe']:.2f}")
        print(f"Team total return: worst {m['total_min']:.1%} | median {m['total_median']:.1%} | best {m['total_max']:.1%}")
        print(f"Team max drawdown: worst {m['dd_worst']:.1%} | median {m['dd_median']:.1%}")
        print(f"Settings with LESS drawdown than {b}: {m['share_less_drawdown_than_bench']:.0%}")
        print(f"Settings beating {b} on return: {m['share_beating_bench_return']:.0%} | on Sharpe: {m['share_beating_bench_sharpe']:.0%}")
        print(f"Settings with a positive result: {m['share_positive']:.0%}")
        return

    if a.mode == "backtest":
        dfs = {s: (synthetic(a.bars, seed=i) if a.synthetic else fetch_klines(s, "1d", a.bars))
               for i, s in enumerate(syms)}
        for s, d in dfs.items():
            print(f"{s}: {len(d)} daily candles, {d.index[0]:%Y-%m-%d} -> {d.index[-1]:%Y-%m-%d}")
        for cash in dict.fromkeys([a.cash or 20.0, 1000.0]):
            r = run_backtest(dfs, cash=cash)
            print(f"\n=== start {cash:,.0f} USDT | {r['period']} | final {r['final_cash']:,.2f} ===")
            print(f"{'':26s}{'total':>9s}{'CAGR':>9s}{'Sharpe':>8s}{'max DD':>9s}")
            for k in ("team", f"{r['bench']} buy&hold", "equal-weight buy&hold"):
                v = r[k]
                print(f"{k:26s}{pct(v['total_return'])}{pct(v['cagr'])}{v['sharpe']:>8.2f}{pct(v['max_drawdown'])}")
            print(f"trades {r['trades']} | win rate {r['win_rate']:.0%} | avg exposure {r['avg_exposure']:.0%} "
                  f"| orders too small for Binance minimum: {r['orders_too_small']}")
            if cash == 1000.0:
                print("ranking when slots are limited (max 5 open):")
                for rk in ("conviction", "per_risk"):
                    x = run_backtest(dfs, cash=cash, rank=rk)["team"]
                    print(f"   {rk:11s} total {x['total_return']:>7.1%}  max DD {x['max_drawdown']:>7.1%}  Sharpe {x['sharpe']:.2f}")
            print("entries blocked by:", r["vetoes"], "| pnl by coin:", r["pnl_by_symbol"])
            print("year   team      " + r["bench"])
            for y, v in r["yearly"].items():
                print(f"{y}  {v['team']:>8.1%}  {v[r['bench']]:>8.1%}")
        return

    if a.mode == "status":
        mrow = build_features(fetch_klines("BTCUSDT", "1d", 400)).iloc[-2].to_dict()
        for s in syms:
            f = build_features(fetch_klines(s, "1d", 400))
            ops = opinions(f.iloc[-2].to_dict(), mrow)
            d = LeadAgent().decide(ops)
            print(f"\n{s}: {'ENTER' if d.enter else 'NO TRADE'}  ({d.reason})")
            for o in ops:
                print(f"   {o.name:11s} score {o.score:+.2f}{'  VETO' if o.veto else '      '}  {o.reason}")
        return

    if a.mode == "paper":
        t = PaperTrader(syms, cash=a.cash or 1000.0, rank=a.rank)
        while True:
            if a.top:
                t.symbols = list(dict.fromkeys(list(t.s["pos"]) + top_symbols(a.top)))
            r = t.step()
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M')}] equity {r['equity']:.2f} USDT"
                  f"{'  (HALTED: drawdown limit)' if r['halted'] else ''}")
            for e in r["events"]:
                print("  ", e)
            for s, act, why in r["table"]:
                print(f"   {s:9s}{act:5s}{why}")
            if not a.loop:
                break
            time.sleep(a.loop)
        return

    import pandas as pd
    j = pd.read_csv("paper_journal.csv")
    e0, e1 = j["equity"].iloc[0], j["equity"].iloc[-1]
    b0, b1 = j["btc"].iloc[0], j["btc"].iloc[-1]
    print(f"{len(j)} readings | paper team {e1 / e0 - 1:+.2%} | holding BTC {b1 / b0 - 1:+.2%}")
    print("BTC wins -> do NOT use real money." if b1 / b0 > e1 / e0 else "Team ahead of BTC so far (short sample).")


if __name__ == "__main__":
    main()
