import logging
import time

from .data import fetch_ohlcv
from .features import FEATURES, add_features, add_label
from .model import LogisticModel
from .risk import Position, RiskConfig, RiskManager

log = logging.getLogger("agent")
HORIZON = 12


class TradingAgent:
    def __init__(self, broker, exchange_id, symbol, timeframe="1h", cfg=None, fetch=fetch_ohlcv):
        self.broker, self.ex_id, self.symbol, self.tf = broker, exchange_id, symbol, timeframe
        self.cfg, self.fetch = cfg or RiskConfig(), fetch
        self.pos, self.model, self.rm, self.last_train = None, None, None, 0

    def _train(self, d):
        d = d.dropna(subset=FEATURES + ["label"])
        self.model = LogisticModel().fit(d[FEATURES].to_numpy(), d["label"].to_numpy())

    def step(self):
        """One decision cycle. Returns a short description of what happened."""
        raw = self.fetch(self.ex_id, self.symbol, self.tf, 1000)
        d = add_label(add_features(raw), HORIZON)
        last, price = d.iloc[-2], float(d["close"].iloc[-1])   # last *closed* bar
        eq = self.broker.equity(price)
        if self.rm is None:
            self.rm = RiskManager(self.cfg, eq)
        self.rm.on_equity(d.index[-1], eq)
        if self.model is None or len(d) - self.last_train >= 200:
            self._train(d.iloc[:-HORIZON - 1])
            self.last_train = len(d)

        if self.pos:
            bar = d.iloc[-1]
            self.pos.update(float(bar["high"]))
            ex = self.pos.check_exit(float(bar["open"]), float(bar["high"]), float(bar["low"]))
            if ex is not None or not self.rm.can_trade(eq) and price < self.pos.entry:
                self.broker.sell(self.symbol, self.pos.qty, price)
                log.info("EXIT %s @ %.4f (entry %.4f)", self.symbol, price, self.pos.entry)
                self.pos = None
                return "exit"
            return "hold"
        if not self.rm.can_trade(eq):
            return "risk-halt"
        p = float(self.model.predict_proba(last[FEATURES].to_numpy(float)[None])[0])
        if p >= self.cfg.entry_threshold:
            qty = self.rm.size(eq, price, float(last["atr"]))
            if qty > 0:
                fill = self.broker.buy(self.symbol, qty, price)
                self.pos = Position(fill, qty, float(last["atr"]), self.cfg)
                log.info("ENTER %s qty=%.6f @ %.4f p=%.2f stop=%.4f tp=%.4f",
                         self.symbol, qty, fill, p, self.pos.stop, self.pos.take_profit)
                return "enter"
        return "wait"

    def run(self, interval=60):
        while True:
            try:
                log.info("step -> %s", self.step())
            except Exception:
                log.exception("step failed; will retry")
            time.sleep(interval)
