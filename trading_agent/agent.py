import csv
import logging
import os
import time
from datetime import datetime, timezone

from .data import fetch_any
from .features import FEATURES, add_features, add_label
from .risk import Portfolio, Position, RiskConfig
from .team import LeadAgent, Team

log = logging.getLogger("agent")
HORIZON = 12


class TradingAgent:
    """Trades one symbol. Several agents can share one Portfolio (account-wide limits)."""

    def __init__(self, broker, exchange_id, symbol, timeframe="1h", cfg=None,
                 fetch=fetch_any, portfolio=None, lead=None):
        self.broker, self.ex_id, self.symbol, self.tf = broker, exchange_id, symbol, timeframe
        self.cfg = cfg or RiskConfig()
        self.fetch = fetch
        self.pf = portfolio or Portfolio(self.cfg)
        self.team, self.lead, self.last_train = Team(), lead or LeadAgent(), 0

    @property
    def pos(self):
        return self.pf.positions.get(self.symbol)

    def _train(self, d):
        d = d.dropna(subset=FEATURES + ["label"])
        self.team.ml.fit_arrays(d[FEATURES].to_numpy(), d["label"].to_numpy())

    def step(self):
        """One decision cycle. Returns a short description of what happened."""
        if not self.broker.is_open():
            return "market-closed"
        raw = self.fetch(self.ex_id, self.symbol, self.tf, 1000)
        d = add_label(add_features(raw), HORIZON)
        last, price = d.iloc[-2], float(d["close"].iloc[-1])   # last *closed* bar
        self.broker.mark(self.symbol, price)
        eq = self.broker.equity(price)
        self.pf.start(d.index[-1], eq)
        rm = self.pf.rm
        if self.team.ml.model is None or len(d) - self.last_train >= 200:
            self._train(d.iloc[:-HORIZON - 1])
            self.last_train = len(d)

        pos = self.pos
        if pos:
            held = self.broker.position_qty(self.symbol)
            if held is not None and held <= 0:  # closed server-side (stop/target hit)
                log.info("EXIT %s closed by broker order", self.symbol)
                del self.pf.positions[self.symbol]
                return "exit"
            bar = d.iloc[-1]
            old_stop = pos.stop
            pos.update(float(bar["high"]))
            if pos.stop > old_stop and hasattr(self.broker, "update_stop"):
                self.broker.update_stop(self.symbol, pos.stop)
            ex = pos.check_exit(float(bar["open"]), float(bar["high"]), float(bar["low"]))
            if ex is not None or (not rm.can_trade(eq) and price < pos.entry):
                self.broker.sell(self.symbol, pos.qty, price)
                log.info("EXIT %s @ %.4f (entry %.4f)", self.symbol, price, pos.entry)
                self.lead.learn(pos.opinions, price - pos.entry)
                del self.pf.positions[self.symbol]
                return "exit"
            return "hold"
        if not rm.can_trade(eq):
            return "risk-halt"
        ops = self.team.opinions(last.to_dict())
        dec = self.lead.decide(ops)
        if not dec.enter:
            log.info("SKIP %s: %s", self.symbol, dec.reason)
            return "wait"
        atr = float(last["atr"])
        stop = price - self.cfg.stop_atr * atr
        qty = rm.size(eq, price, atr) * dec.size_mult
        qty = self.pf.cap_qty(self.symbol, qty, price, stop, eq, self.broker.buying_power())
        qty = self.broker.normalize_qty(qty)
        if qty <= 0:
            return "limit"  # portfolio limits or no cash
        pos = Position(price, qty, atr, self.cfg)
        if getattr(self.broker, "supports_bracket", False):
            fill = self.broker.buy(self.symbol, qty, price, pos.stop, pos.take_profit)
        else:
            fill = self.broker.buy(self.symbol, qty, price)
        pos.opinions = {o.name: o.score for o in ops}
        self.pf.positions[self.symbol] = pos
        log.info("ENTER %s qty=%.6f @ %.4f %s stop=%.4f tp=%.4f",
                 self.symbol, qty, fill, dec.reason, pos.stop, pos.take_profit)
        return "enter"


class PortfolioRunner:
    """Runs one agent per symbol under shared account-wide risk limits."""

    def __init__(self, broker, exchange_id, symbols, timeframe="1h", cfg=None, fetch=fetch_any):
        self.cfg = cfg or RiskConfig()
        self.pf = Portfolio(self.cfg)
        self.lead = LeadAgent()  # one lead agent supervises every symbol's specialists
        self.agents = [TradingAgent(broker, exchange_id, s, timeframe, self.cfg, fetch, self.pf, self.lead)
                       for s in symbols]

    def step(self):
        """Manage open positions first, so exits free risk budget before new entries."""
        results = {}
        for a in sorted(self.agents, key=lambda a: a.pos is None):
            try:
                results[a.symbol] = a.step()
            except Exception:
                log.exception("%s step failed; will retry", a.symbol)
                results[a.symbol] = "error"
        return results

    def journal(self, path="journal.csv"):
        """Append account equity to a CSV so the run can be compared with a benchmark."""
        eq = self.agents[0].broker.equity()
        new = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["utc", "equity", "open_positions"])
            w.writerow([datetime.now(timezone.utc).isoformat(), round(eq, 2), len(self.pf.positions)])

    def run(self, interval=60):
        while True:
            log.info("cycle -> %s", self.step())
            try:
                self.journal()
            except Exception:
                log.exception("journal failed")
            time.sleep(interval)
