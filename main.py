import argparse
import logging

from trading_agent.agent import PortfolioRunner
from trading_agent.backtest import run_backtest
from trading_agent.broker import AlpacaBroker, CcxtBroker, PaperBroker
from trading_agent.data import fetch_any, synthetic_ohlcv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backtest", "paper", "live"])
    ap.add_argument("--exchange", default="binance", help="ccxt exchange id, or 'alpaca' for US stocks")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--symbols", help="comma-separated list, e.g. AAPL,MSFT,NVDA (overrides --symbol)")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--synthetic", action="store_true", help="backtest on fake data (offline)")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    symbols = [x.strip() for x in a.symbols.split(",")] if a.symbols else [a.symbol]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
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
