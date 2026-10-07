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


def test_portfolio_limits_and_multi_symbol():
    from trading_agent.agent import PortfolioRunner
    from trading_agent.risk import Portfolio
    cfg = RiskConfig(max_positions=2, max_portfolio_risk=0.02, max_exposure=0.5)
    pf = Portfolio(cfg)
    pf.start(__import__("pandas").Timestamp("2024-01-01"), 10_000)
    # risk budget 2% = 200 -> at 5 risk/unit, max 40 units even if 1000 requested
    assert pf.cap_qty("A", 1000, 100, 95, 10_000) == 40
    pf.positions["A"] = Position(100, 40, 3.33, cfg)
    assert pf.cap_qty("A", 10, 100, 95, 10_000) == 0          # already held
    pf.positions["B"] = Position(100, 1, 3.33, cfg)
    assert pf.cap_qty("C", 10, 100, 95, 10_000) == 0          # max_positions
    assert Portfolio(cfg).cap_qty("X", 1000, 100, 95, 10_000, cash=500) < 5.1  # cash cap

    data = {s: synthetic_ohlcv(1200, seed=i) for i, s in enumerate(["A", "B", "C"])}
    broker = PaperBroker()
    runner = PortfolioRunner(broker, "x", list(data), cfg=cfg,
                             fetch=lambda ex, sym, tf, n: data[sym])
    for _ in range(3):
        res = runner.step()
    assert set(res) == {"A", "B", "C"}
    assert len(runner.pf.positions) <= 2
    assert broker.cash > -1e-6


def test_shared_portfolio_backtest_respects_limits():
    from trading_agent.portfolio_backtest import run_portfolio_backtest
    dfs = {s: synthetic_ohlcv(2500, seed=i) for i, s in enumerate(["A", "B", "C", "D"])}
    cfg = RiskConfig(max_positions=2, max_exposure=0.5)
    r = run_portfolio_backtest(dfs, cfg)
    assert r["max_open_positions"] <= 2
    assert r["avg_exposure"] <= 0.5 + 1e-9
    assert r["final_equity"] > 0 and r["max_drawdown"] <= 0
    assert set(r["pnl_by_symbol"]) == set(dfs)


def test_portfolio_backtest_rejects_too_little_data():
    import pytest
    from trading_agent.portfolio_backtest import run_portfolio_backtest
    with pytest.raises(ValueError, match="bars"):
        run_portfolio_backtest({"A": synthetic_ohlcv(120), "B": synthetic_ohlcv(120, seed=1)})


def test_alpaca_pagination(monkeypatch):
    import requests
    from trading_agent import data
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET", "s")
    pages = [
        {"bars": [{"t": "2024-01-02T14:00:00Z", "o": 1, "h": 2, "l": 1, "c": 2, "v": 5}], "next_page_token": "x"},
        {"bars": [{"t": "2024-01-02T15:00:00Z", "o": 2, "h": 3, "l": 2, "c": 3, "v": 5}], "next_page_token": None},
    ]

    class R:
        def __init__(self, j): self.j = j
        def raise_for_status(self): pass
        def json(self): return self.j
    monkeypatch.setattr(requests, "get", lambda *a, **k: R(pages.pop(0)))
    assert len(data.fetch_alpaca_bars("alpaca", "AAPL")) == 2


def test_team_vetoes_and_lead_logic():
    from trading_agent.team import LeadAgent, Team
    team, lead = Team(), LeadAgent()
    good = dict(trend=0.05, trend_slope=0.01, vol_ratio=0.8, r20=0.04, ema_ratio=0.01)
    ops = team.opinions(good)
    assert not any(o.veto for o in ops)
    down = dict(good, trend=-0.03)
    d = lead.decide(team.opinions(down))
    assert not d.enter and "regime" in d.reason          # downtrend veto
    panic = dict(good, vol_ratio=3.5)
    assert "volatility" in lead.decide(team.opinions(panic)).reason
    assert not lead.decide(ops, account_ok=False).enter  # risk officer
    w0 = lead.w["momentum"]
    lead.learn({"momentum": 0.5}, -10)
    assert lead.w["momentum"] < w0                        # backers of a loser lose weight


def test_team_backtest_and_live_step():
    from trading_agent.portfolio_backtest import run_portfolio_backtest
    dfs = {s: synthetic_ohlcv(2500, seed=i) for i, s in enumerate("ABC")}
    for strat in ("team", "ml"):
        r = run_portfolio_backtest(dfs, strategy=strat)
        assert r["final_equity"] > 0
    ag = TradingAgent(PaperBroker(), "x", "SYN", fetch=lambda *a: synthetic_ohlcv(1500, seed=3))
    assert ag.step() in {"enter", "wait", "hold", "exit", "risk-halt", "limit"}


def test_trend_portfolio_cuts_crash_drawdown():
    import numpy as np, pandas as pd
    from trading_agent.trend import run_trend_backtest
    n = 1800
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rng = np.random.default_rng(0)
    drift = np.where((np.arange(n) > 900) & (np.arange(n) < 1100), -0.0035, 0.0006)
    def mk(seed):
        r = drift + np.random.default_rng(seed).normal(0, 0.008, n)
        c = 100 * np.exp(np.cumsum(r))
        return pd.DataFrame({"close": c}, index=idx)
    res = run_trend_backtest({"A": mk(1), "B": mk(2)}, benchmark="A")
    assert res["strategy"]["max_drawdown"] > res["A buy&hold"]["max_drawdown"]
    assert "allocation_now" in res and res["yearly"]
