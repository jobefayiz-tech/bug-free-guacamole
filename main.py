import argparse
import logging

from trading_agent.agent import TradingAgent
from trading_agent.backtest import run_backtest
from trading_agent.broker import AlpacaBroker, CcxtBroker, PaperBroker
from trading_agent.data import fetch_any, synthetic_ohlcv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backtest", "paper", "live"])
    ap.add_argument("--exchange", default="binance", help="ccxt exchange id, or 'alpaca' for US stocks")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--synthetic", action="store_true", help="backtest on fake data (offline)")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if a.mode == "backtest":
        df = synthetic_ohlcv() if a.synthetic else fetch_any(a.exchange, a.symbol, a.timeframe, 1000)
        for k, v in run_backtest(df, warmup=min(500, len(df) // 3)).items():
            print(f"{k:14s} {v}")
        return
    if a.mode == "paper":
        broker = PaperBroker()
    elif a.exchange == "alpaca":
        broker = AlpacaBroker()  # Alpaca paper account unless LIVE_TRADING=yes
    else:
        broker = CcxtBroker(a.exchange)
    TradingAgent(broker, a.exchange, a.symbol, a.timeframe).run(a.interval)


if __name__ == "__main__":
    main()
