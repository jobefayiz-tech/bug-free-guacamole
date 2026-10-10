"""Binance team CLI (paper trading only).
  python crypto.py backtest [--cash 20] [--synthetic]
  python crypto.py status            today's decision of every specialist for every coin
  python crypto.py paper [--loop 3600]
  python crypto.py report            paper result vs just holding BTC
"""
import argparse
import time

from binance_team.agents import LeadAgent, build_features, opinions
from binance_team.backtest import run_backtest
from binance_team.data import fetch_klines, synthetic
from binance_team.paper import PaperTrader

DEFAULT = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT"


def pct(x):
    return f"{x:>8.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backtest", "status", "paper", "report"])
    ap.add_argument("--symbols", default=DEFAULT)
    ap.add_argument("--cash", type=float, default=20.0)
    ap.add_argument("--bars", type=int, default=2500)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--loop", type=int, default=0, help="paper: repeat every N seconds")
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",")]

    if a.mode == "backtest":
        dfs = {s: (synthetic(a.bars, seed=i) if a.synthetic else fetch_klines(s, "1d", a.bars))
               for i, s in enumerate(syms)}
        for s, d in dfs.items():
            print(f"{s}: {len(d)} daily candles, {d.index[0]:%Y-%m-%d} -> {d.index[-1]:%Y-%m-%d}")
        for cash in dict.fromkeys([a.cash, 1000.0]):
            r = run_backtest(dfs, cash=cash)
            print(f"\n=== start {cash:,.0f} USDT | {r['period']} | final {r['final_cash']:,.2f} ===")
            print(f"{'':26s}{'total':>9s}{'CAGR':>9s}{'Sharpe':>8s}{'max DD':>9s}")
            for k in ("team", f"{r['bench']} buy&hold", "equal-weight buy&hold"):
                v = r[k]
                print(f"{k:26s}{pct(v['total_return'])}{pct(v['cagr'])}{v['sharpe']:>8.2f}{pct(v['max_drawdown'])}")
            print(f"trades {r['trades']} | win rate {r['win_rate']:.0%} | avg exposure {r['avg_exposure']:.0%} "
                  f"| orders too small for Binance minimum: {r['orders_too_small']}")
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
        t = PaperTrader(syms, cash=a.cash)
        while True:
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
