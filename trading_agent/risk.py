from dataclasses import dataclass


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.01      # fraction of equity risked per trade
    max_position_frac: float = 0.5    # max notional as fraction of equity
    stop_atr: float = 1.5
    take_profit_atr: float = 2.5
    breakeven_atr: float = 1.0        # after this profit, stop moves to breakeven (+fees)
    trail_start_atr: float = 1.5
    trail_atr: float = 1.0
    fee_rate: float = 0.001
    slippage: float = 0.0005
    daily_loss_limit: float = 0.03    # stop trading for the day
    max_drawdown: float = 0.15        # kill switch: stop trading entirely
    entry_threshold: float = 0.60     # min model probability to enter


class Position:
    def __init__(self, entry, qty, atr, cfg: RiskConfig):
        self.entry, self.qty, self.atr, self.cfg = entry, qty, atr, cfg
        self.stop = entry - cfg.stop_atr * atr
        self.take_profit = entry + cfg.take_profit_atr * atr
        self.highest = entry

    def update(self, high):
        """Raise the stop as profit grows. The stop never moves down."""
        c = self.cfg
        self.highest = max(self.highest, high)
        gain = self.highest - self.entry
        if gain >= c.breakeven_atr * self.atr:
            self.stop = max(self.stop, self.entry * (1 + 2 * (c.fee_rate + c.slippage)))
        if gain >= c.trail_start_atr * self.atr:
            self.stop = max(self.stop, self.highest - c.trail_atr * self.atr)

    def check_exit(self, open_, high, low):
        """Return exit price or None. Stop is assumed hit before target within a bar."""
        if low <= self.stop:
            return min(self.stop, open_)  # gap-down fills at open, not at stop
        if high >= self.take_profit:
            return self.take_profit
        return None


class RiskManager:
    def __init__(self, cfg: RiskConfig, equity):
        self.cfg, self.peak, self.day, self.day_start = cfg, equity, None, equity

    def on_equity(self, ts, equity):
        day = ts.date() if hasattr(ts, "date") else ts
        if day != self.day:
            self.day, self.day_start = day, equity
        self.peak = max(self.peak, equity)

    def can_trade(self, equity):
        if equity < self.peak * (1 - self.cfg.max_drawdown):
            return False
        return equity > self.day_start * (1 - self.cfg.daily_loss_limit)

    def size(self, equity, entry, atr):
        c = self.cfg
        risk_per_unit = c.stop_atr * atr
        qty = equity * c.risk_per_trade / risk_per_unit
        return min(qty, equity * c.max_position_frac / entry)
