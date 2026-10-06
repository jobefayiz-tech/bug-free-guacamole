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
    max_positions: int = 5            # portfolio: max simultaneous open positions
    max_portfolio_risk: float = 0.04  # portfolio: max total equity at risk (entry-to-stop)
    max_exposure: float = 0.8         # portfolio: max total notional as fraction of equity


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


class Portfolio:
    """Shared state for many symbols: open positions plus account-wide risk limits."""

    def __init__(self, cfg: RiskConfig):
        self.cfg, self.rm, self.positions = cfg, None, {}

    def start(self, ts, equity):
        if self.rm is None:
            self.rm = RiskManager(self.cfg, equity)
        self.rm.on_equity(ts, equity)

    def open_risk(self):
        return sum(max(p.entry - p.stop, 0) * p.qty for p in self.positions.values())

    def exposure(self):
        return sum(p.entry * p.qty for p in self.positions.values())

    def cap_qty(self, symbol, qty, entry, stop, equity, cash=None):
        """Shrink qty so the new trade respects portfolio limits (0 = not allowed)."""
        c = self.cfg
        if symbol in self.positions or len(self.positions) >= c.max_positions:
            return 0.0
        qty = min(qty, (equity * c.max_exposure - self.exposure()) / entry)
        if entry > stop:
            qty = min(qty, (equity * c.max_portfolio_risk - self.open_risk()) / (entry - stop))
        if cash is not None:
            qty = min(qty, cash / (entry * (1 + c.fee_rate)))
        return max(qty, 0.0)
