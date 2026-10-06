from trading_agent.agent import TradingAgent
from trading_agent.backtest import run_backtest
from trading_agent.broker import PaperBroker
from trading_agent.data import synthetic_ohlcv
from trading_agent.risk import Position, RiskConfig, RiskManager


def test_stop_never_moves_down_and_reaches_breakeven():
    cfg = RiskConfig()
    p = Position(100, 1, 2, cfg)
    s0 = p.stop
    p.update(103)  # +1.5 ATR
    assert p.stop > 100 and p.stop >= s0
    s1 = p.stop
    p.update(101)
    assert p.stop == s1


def test_gap_down_fills_at_open():
    p = Position(100, 1, 2, RiskConfig())
    assert p.check_exit(90, 91, 89) == 90


def test_risk_halts_after_daily_loss():
    import pandas as pd
    rm = RiskManager(RiskConfig(), 1000)
    rm.on_equity(pd.Timestamp("2024-01-01 10:00"), 1000)
    assert rm.can_trade(1000)
    assert not rm.can_trade(960)


def test_backtest_runs():
    r = run_backtest(synthetic_ohlcv(2500, seed=1))
    assert r["final_equity"] > 0 and r["max_drawdown"] <= 0


def test_agent_step_paper():
    df = synthetic_ohlcv(1200, seed=2)
    ag = TradingAgent(PaperBroker(), "x", "SYN", fetch=lambda *a: df)
    assert ag.step() in {"enter", "wait", "hold", "exit", "risk-halt"}


def test_alpaca_bracket_order_and_stop_update(monkeypatch):
    import requests
    from trading_agent.broker import AlpacaBroker
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET", "s")
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    calls = []

    class R:
        content = b"1"
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data

    def fake(method, url, **kw):
        calls.append((method, url, kw.get("json")))
        if url.endswith("/v2/orders") and method == "GET":
            return R([{"id": "p", "type": "limit", "legs": [{"id": "s1", "type": "stop"}]}])
        return R({})
    monkeypatch.setattr(requests, "request", fake)
    b = AlpacaBroker()
    assert "paper-api" in b.base and b.normalize_qty(3.9) == 3.0
    b.buy("AAPL", 3, 100, 98.5, 105)
    body = calls[0][2]
    assert body["order_class"] == "bracket" and body["stop_loss"]["stop_price"] == "98.50"
    b.update_stop("AAPL", 101)
    assert any(c[0] == "PATCH" and c[1].endswith("/s1") for c in calls)
