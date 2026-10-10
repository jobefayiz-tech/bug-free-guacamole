"""Paper (fake-money) trader with the same rules as the backtest. State survives restarts."""
import csv
import json
import os
from datetime import datetime, timezone

from .agents import LeadAgent, build_features, opinions
from .data import fetch_klines


class PaperTrader:
    def __init__(self, symbols, cash=20.0, market="BTCUSDT", interval="1d", state="paper_state.json",
                 journal="paper_journal.csv", fetch=fetch_klines, fee=0.001, slip=0.0005, risk=0.02,
                 max_pos_frac=0.5, min_notional=5.0, stop_atr=2.5, trail_atr=3.0,
                 lock_start_atr=2.0, lock_frac=0.4, halt_drawdown=0.30):
        self.__dict__.update(locals())
        self.lead = LeadAgent()
        self.s = {"cash": cash, "peak": cash, "pos": {}, "log": []}
        if os.path.exists(state):
            self.s = json.load(open(state))

    def _save(self):
        json.dump(self.s, open(self.state, "w"), indent=1)

    def step(self):
        feats, cur = {}, {}
        for sym in dict.fromkeys(self.symbols + [self.market]):
            df = self.fetch(sym, self.interval, 400)
            feats[sym], cur[sym] = build_features(df), df.iloc[-1]
        mrow = feats[self.market].iloc[-2].to_dict()
        today = str(feats[self.market].index[-1].date())
        price = {s: float(c["close"]) for s, c in cur.items()}
        pos, events, table = self.s["pos"], [], []
        decisions = {s: self.lead.decide(opinions(feats[s].iloc[-2].to_dict(), mrow)) for s in self.symbols}

        for s in list(pos):                                  # manage open positions
            p, c = pos[s], cur[s]
            fresh = p["day"] != today
            hi, lo = (float(c["high"]), float(c["low"])) if fresh else (price[s], price[s])
            exit_px = None
            if lo <= p["stop"]:
                exit_px, why = p["stop"], "stop"
            elif not decisions[s].hold:
                exit_px, why = price[s], "trend/market broke"
            if exit_px is not None:
                exit_px *= 1 - self.slip
                self.s["cash"] += p["qty"] * exit_px * (1 - self.fee)
                pnl = p["qty"] * (exit_px - p["entry"]) - self.fee * p["qty"] * (exit_px + p["entry"])
                self.s["log"].append([today, s, "SELL", round(exit_px, 6), round(pnl, 4), why])
                events.append(f"SELL {s} @ {exit_px:.4f} pnl {pnl:+.2f} ({why})")
                del pos[s]
                continue
            p["high"] = max(p["high"], hi)
            gain = p["high"] - p["entry"]
            p["stop"] = max(p["stop"], p["high"] - self.trail_atr * p["atr"])
            if gain >= self.lock_start_atr * p["atr"]:
                p["stop"] = max(p["stop"], p["entry"] + self.lock_frac * gain)

        eq = self.s["cash"] + sum(p["qty"] * price[s] for s, p in pos.items())
        self.s["peak"] = max(self.s["peak"], eq)
        halted = self.halt_drawdown is not None and eq < self.s["peak"] * (1 - self.halt_drawdown)
        for s in self.symbols:                               # new entries
            d = decisions[s]
            table.append((s, "HOLD" if s in pos else ("BUY" if d.enter else "no"), d.reason))
            if s in pos or not d.enter or halted:
                continue
            atr = float(feats[s].iloc[-2]["atr"])
            px, dist = price[s] * (1 + self.slip), self.stop_atr * atr
            qty = min(eq * self.risk / dist * d.size, eq * self.max_pos_frac / px,
                      self.s["cash"] / (px * (1 + self.fee)))
            if qty * px < self.min_notional:
                events.append(f"skip {s}: order {qty * px:.2f} USDT is below the {self.min_notional} minimum")
                continue
            self.s["cash"] -= qty * px * (1 + self.fee)
            pos[s] = dict(qty=qty, entry=px, stop=px - dist, high=px, atr=atr, day=today)
            self.s["log"].append([today, s, "BUY", round(px, 6), 0, d.reason])
            events.append(f"BUY {s} qty {qty:.6f} @ {px:.4f} stop {px - dist:.4f} ({d.reason})")

        eq = self.s["cash"] + sum(p["qty"] * price[s] for s, p in pos.items())
        self._save()
        new = not os.path.exists(self.journal)
        with open(self.journal, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["utc", "equity", "btc"])
            w.writerow([datetime.now(timezone.utc).isoformat(), round(eq, 4), price.get("BTCUSDT", "")])
        return {"equity": eq, "events": events, "table": table, "halted": halted, "positions": dict(pos)}
