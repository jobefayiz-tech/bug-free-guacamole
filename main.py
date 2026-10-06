import argparse
import logging

from trading_agent.agent import PortfolioRunner
from trading_agent.backtest import run_backtest
from trading_agent.broker import AlpacaBroker, CcxtBroker, PaperBroker
from trading_agent.data import fetch_any, synthetic_ohlcv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backtest", "paper", "live", "report"])
    ap.add_argument("--exchange", default="binance", help="ccxt exchange id, or 'alpaca' for US stocks")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--symbols", help="comma-separated list, e.g. AAPL,MSFT,NVDA (overrides --symbol)")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--synthetic", action="store_true", help="backtest on fake data (offline)")
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
