"""Paper (fake-money) trader with the same rules as the backtest. State survives restarts.

Safety layer in code (not in any model): data-error kill switch, daily loss limit, drawdown halt,
position cap. Every trade is written to paper_trades.csv with the reason and each agent's score."""
import csv
import json
import os
from datetime import datetime, timezone

import pandas as pd

from .agents import LeadAgent, build_features, opinions
from .data import fetch_klines

TRADE_COLS = ["date", "symbol", "action", "price", "qty", "pnl", "reason", "agent_scores", "stop", "equity"]


class PaperTrader:
    def __init__(self, symbols, cash=20.0, market="BTCUSDT", interval="1d", state="paper_state.json",
                 journal="paper_journal.csv", trades_csv="paper_trades.csv", fetch=fetch_klines,
                 fee=0.001, slip=0.0005, risk=0.02, max_pos_frac=0.5, min_notional=5.0, stop_atr=2.5,
                 trail_atr=3.0, lock_start_atr=2.0, lock_frac=0.4, halt_drawdown=0.30,
                 daily_loss_limit=0.03, max_positions=5, rank="conviction", max_age_days=2):
        self.__dict__.update(locals())
        self.lead = LeadAgent()
        self.s = {"cash": cash, "peak": cash, "pos": {}, "log": [], "day": None, "day_start": cash}
        if os.path.exists(state):
            self.s.update(json.load(open(state)))

    def _save(self):
        json.dump(self.s, open(self.state, "w"), indent=1)

    def _trade(self, row):
        new = not os.path.exists(self.trades_csv)
        with open(self.trades_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(TRADE_COLS)
            w.writerow(row)

    def _load(self, sym, errors):
        try:
            df = self.fetch(sym, self.interval, 400)
            if len(df) < 250:
                raise ValueError(f"only {len(df)} candles")
            if self.max_age_days is not None:
                age = pd.Timestamp.now(tz="UTC").tz_localize(None) - df.index[-1]
                if age > pd.Timedelta(days=self.max_age_days):
                    raise ValueError(f"stale data (last candle {age.days} days old)")
            return build_features(df), df.iloc[-1]
        except Exception as e:  # network, symbol delisted, bad data: skip this symbol, never crash
            errors.append(f"{sym}: {e}")
            return None, None

    def step(self):
        feats, cur, events = {}, {}, []
        for sym in dict.fromkeys(self.symbols + [self.market]):
            feats[sym], cur[sym] = self._load(sym, events)
        feats = {k: v for k, v in feats.items() if v is not None}
        cur = {k: v for k, v in cur.items() if v is not None}
        events = [f"DATA ERROR {e}" for e in events]
        market_ok = self.market in feats
        if not market_ok:
            events.append("KILL SWITCH: no reliable market (BTC) data -> no new entries, no forced exits")
        mrow = feats[self.market].iloc[-2].to_dict() if market_ok else None
        today = str(feats[self.market].index[-1].date()) if market_ok else datetime.now(timezone.utc).date().isoformat()
        price = {s: float(c["close"]) for s, c in cur.items()}
        pos, table, ops_by = self.s["pos"], [], {}
        decisions = {}
        if market_ok:
            for s in self.symbols:
                if s in feats:
                    ops_by[s] = opinions(feats[s].iloc[-2].to_dict(), mrow)
                    decisions[s] = self.lead.decide(ops_by[s])

        for s in list(pos):                                  # manage open positions
            p = pos[s]
            if s not in cur:
                events.append(f"{s}: no data this cycle, position left unmanaged")
                continue
            c = cur[s]
            fresh = p["day"] != today
            hi, lo = (float(c["high"]), float(c["low"])) if fresh else (price[s], price[s])
            exit_px = None
            if lo <= p["stop"]:
                exit_px, why = p["stop"], "stop hit"
            elif s in decisions and not decisions[s].hold:
                exit_px, why = price[s], "trend/market broke: " + decisions[s].reason
            if exit_px is not None:
                exit_px *= 1 - self.slip
                self.s["cash"] += p["qty"] * exit_px * (1 - self.fee)
                pnl = p["qty"] * (exit_px - p["entry"]) - self.fee * p["qty"] * (exit_px + p["entry"])
                self.s["log"].append([today, s, "SELL", round(exit_px, 6), round(pnl, 4), why])
                events.append(f"SELL {s} @ {exit_px:.4f} pnl {pnl:+.2f} ({why})")
                self._trade([today, s, "SELL", round(exit_px, 6), round(p["qty"], 8), round(pnl, 4), why,
                             json.dumps(p.get("scores", {})), round(p["stop"], 6), ""])
                del pos[s]
                continue
            p["high"] = max(p["high"], hi)
            gain = p["high"] - p["entry"]
            p["stop"] = max(p["stop"], p["high"] - self.trail_atr * p["atr"])
            if gain >= self.lock_start_atr * p["atr"]:
                p["stop"] = max(p["stop"], p["entry"] + self.lock_frac * gain)

        eq = self.s["cash"] + sum(p["qty"] * price.get(s, p["entry"]) for s, p in pos.items())
        if self.s.get("day") != today:                       # first check of a new day
            self.s["day"], self.s["day_start"] = today, eq
        self.s["peak"] = max(self.s["peak"], eq)
        dd_halt = self.halt_drawdown is not None and eq < self.s["peak"] * (1 - self.halt_drawdown)
        day_halt = self.daily_loss_limit is not None and eq < self.s["day_start"] * (1 - self.daily_loss_limit)
        halted = dd_halt or day_halt or not market_ok
        if dd_halt:
            events.append(f"HALT: drawdown over {self.halt_drawdown:.0%} from peak -> no new entries")
        if day_halt:
            events.append(f"HALT: lost more than {self.daily_loss_limit:.0%} today -> no new entries today")

        def key(x):
            d = decisions[x]
            if self.rank == "conviction":
                return -d.score
            atr_ = float(feats[x].iloc[-2]["atr"])
            return -d.score * price[x] / (self.stop_atr * atr_) if atr_ > 0 else 0
        for s in sorted(decisions, key=key):                 # new entries, best first
            d = decisions[s]
            table.append((s, "HOLD" if s in pos else ("BUY" if d.enter else "no"), d.reason))
            if s in pos or not d.enter or halted or len(pos) >= self.max_positions:
                continue
            atr = float(feats[s].iloc[-2]["atr"])
            px, dist = price[s] * (1 + self.slip), self.stop_atr * atr
            qty = min(eq * self.risk / dist * d.size, eq * self.max_pos_frac / px,
                      self.s["cash"] / (px * (1 + self.fee)))
            if qty * px < self.min_notional:
                events.append(f"skip {s}: order {qty * px:.2f} USDT is below the {self.min_notional} minimum")
                continue
            self.s["cash"] -= qty * px * (1 + self.fee)
            scores = {o.name: round(o.score, 3) for o in ops_by[s]}
            pos[s] = dict(qty=qty, entry=px, stop=px - dist, high=px, atr=atr, day=today, scores=scores)
            self.s["log"].append([today, s, "BUY", round(px, 6), 0, d.reason])
            events.append(f"BUY {s} qty {qty:.6f} @ {px:.4f} stop {px - dist:.4f} "
                          f"(risk {qty * dist:.2f} USDT) ({d.reason})")
            self._trade([today, s, "BUY", round(px, 6), round(qty, 8), 0, d.reason, json.dumps(scores),
                         round(px - dist, 6), round(eq, 4)])

        eq = self.s["cash"] + sum(p["qty"] * price.get(s, p["entry"]) for s, p in pos.items())
        self._save()
        new = not os.path.exists(self.journal)
        with open(self.journal, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["utc", "equity", "btc"])
            w.writerow([datetime.now(timezone.utc).isoformat(), round(eq, 4), price.get("BTCUSDT", "")])
        return {"equity": eq, "events": events, "table": table, "halted": halted, "positions": dict(pos)}
