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
