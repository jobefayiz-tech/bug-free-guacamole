import argparse
import logging
import os

from trading_agent.agent import PortfolioRunner
from trading_agent.backtest import run_backtest
from trading_agent.broker import AlpacaBroker, CcxtBroker, PaperBroker
from trading_agent.portfolio_backtest import run_portfolio_backtest
from trading_agent.risk import RiskConfig
from trading_agent.data import fetch_any, synthetic_ohlcv


def load_env(path=".env"):
    """Read KEY=VALUE lines from .env into the environment (no extra packages needed)."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backtest", "paper", "live", "report"])
    ap.add_argument("--exchange", default="binance", help="ccxt exchange id, or 'alpaca' for US stocks")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--symbols", help="comma-separated list, e.g. AAPL,MSFT,NVDA (overrides --symbol)")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--synthetic", action="store_true", help="backtest on fake data (offline)")
    ap.add_argument("--shared", action="store_true",
                    help="backtest: simulate ONE shared portfolio (cash pool + account-wide limits)")
    ap.add_argument("--benchmark", default="SPY", help="report: stock to compare against")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    symbols = [x.strip() for x in a.symbols.split(",")] if a.symbols else [a.symbol]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if a.mode == "report":
        import pandas as pd
        j = pd.read_csv("journal.csv", parse_dates=["utc"])
        agent_ret = j["equity"].iloc[-1] / j["equity"].iloc[0] - 1
        b = fetch_any("alpaca", a.benchmark, "1d", 400)
        b.index = b.index.tz_convert("UTC") if b.index.tz else b.index.tz_localize("UTC")
        b = b["close"]
        t0, t1 = j["utc"].iloc[0], j["utc"].iloc[-1]
        b0, b1 = b[:t0].iloc[-1], b[:t1].iloc[-1]
        print(f"period       {t0:%Y-%m-%d} -> {t1:%Y-%m-%d}")
        print(f"agent        {agent_ret:+.2%}")
        print(f"{a.benchmark:12s} {b1 / b0 - 1:+.2%}")
        print("verdict      " + ("agent beat benchmark" if agent_ret > b1 / b0 - 1
                                 else "benchmark wins: do NOT go live"))
        return
    if a.mode == "backtest" and a.shared:
        dfs = {sym: (synthetic_ohlcv(seed=n) if a.synthetic else fetch_any(a.exchange, sym, a.timeframe, 1000))
               for n, sym in enumerate(symbols)}
        w = min(500, min(len(d) for d in dfs.values()) // 3)
        loose = RiskConfig(max_positions=len(symbols), max_portfolio_risk=1.0, max_exposure=1.0)
        for title, cfg in (("WITH shared limits (default)", RiskConfig()), ("NO portfolio limits", loose)):
            print(f"== {title}")
            for k, v in run_portfolio_backtest(dfs, cfg, warmup=w).items():
                print(f"{k:28s} {v}")
        return
    if a.mode == "backtest":
        for n, sym in enumerate(symbols):
            df = synthetic_ohlcv(seed=n) if a.synthetic else fetch_any(a.exchange, sym, a.timeframe, 1000)
            print(f"== {sym} (independent per-symbol backtest)")
            for k, v in run_backtest(df, warmup=min(500, len(df) // 3)).items():
                print(f"{k:14s} {v}")
        return
    if a.mode == "paper":
        broker = PaperBroker()
    elif a.exchange == "alpaca":
        broker = AlpacaBroker()  # Alpaca paper account unless LIVE_TRADING=yes
    else:
        broker = CcxtBroker(a.exchange)
    PortfolioRunner(broker, a.exchange, symbols, a.timeframe).run(a.interval)


if __name__ == "__main__":
    main()
