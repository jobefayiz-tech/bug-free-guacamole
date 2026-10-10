import json

import pytest

from binance_team import data
from binance_team.agents import LeadAgent, build_features, opinions
from binance_team.backtest import run_backtest
from binance_team.data import synthetic
from binance_team.paper import PaperTrader

GOOD = dict(px_vs_200=0.10, gap=0.05, slope200=0.02, roc20=0.10, roc60=0.20, rsi=60,
            vol20=0.03, vol_ratio=1.0, vol_x=1.2, dollar_vol=1e8)


def test_each_agent_and_lead():
    lead = LeadAgent()
    assert lead.decide(opinions(GOOD, GOOD)).enter
    down = dict(GOOD, px_vs_200=-0.05)
    d = lead.decide(opinions(down, GOOD))
    assert not d.enter and not d.hold and "trend" in d.reason      # structural veto -> leave position
    d = lead.decide(opinions(GOOD, dict(GOOD, slope200=-0.01)))
    assert not d.enter and not d.hold and "market" in d.reason      # BTC down -> no trade
    d = lead.decide(opinions(dict(GOOD, vol_ratio=4), GOOD))
    assert not d.enter and d.hold                                   # volatility blocks entry only
    assert not lead.decide(opinions(dict(GOOD, dollar_vol=1e5), GOOD)).enter   # illiquid
    assert not lead.decide(opinions(dict(GOOD, rsi=95), GOOD)).enter           # overheated
    assert lead.decide(opinions(dict(GOOD, vol20=0.12), GOOD)).size < 0.5      # wild -> small size
    assert not lead.decide(opinions(GOOD, None)).enter                          # no market data


def test_backtest_runs_with_small_cash():
    dfs = {s: synthetic(2500, seed=i) for i, s in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT"])}
    r = run_backtest(dfs, cash=20.0)
    assert r["final_cash"] > 0 and r["team"]["max_drawdown"] <= 0
    assert 0 <= r["avg_exposure"] <= 1.0 + 1e-9
    assert set(r["pnl_by_symbol"]) == set(dfs)


def test_backtest_needs_enough_data():
    with pytest.raises(ValueError):
        run_backtest({"BTCUSDT": synthetic(300)})


def test_klines_paging(monkeypatch):
    def row(t):
        return [t, "1", "2", "0.5", "1.5", "10", 0, 0, 0, 0, 0, 0]
    pages = [[row(1000 + i * 86400000) for i in range(1000)],
             [row(i * 86400000) for i in range(1, 501)]]
    monkeypatch.setattr(data, "_get", lambda path, params: pages.pop(0))
    df = data.fetch_klines("BTCUSDT", "1d", 1500)
    assert len(df) == 1500 and df.index.is_monotonic_increasing


def test_paper_trader_persists_and_respects_minimum(tmp_path):
    frames = {s: synthetic(600, seed=i) for i, s in enumerate(["BTCUSDT", "ETHUSDT"])}
    kw = dict(state=str(tmp_path / "s.json"), journal=str(tmp_path / "j.csv"),
              fetch=lambda sym, itv, n: frames[sym])
    t = PaperTrader(["BTCUSDT", "ETHUSDT"], cash=20.0, **kw)
    r = t.step()
    assert r["equity"] > 0 and len(r["table"]) == 2
    saved = json.load(open(tmp_path / "s.json"))
    t2 = PaperTrader(["BTCUSDT", "ETHUSDT"], cash=999.0, **kw)   # restart: state reloaded, not reset
    assert t2.s["cash"] == pytest.approx(saved["cash"])
    assert (tmp_path / "j.csv").exists()
    tiny = PaperTrader(["BTCUSDT"], cash=2.0, state=str(tmp_path / "t.json"),
                       journal=str(tmp_path / "tj.csv"), fetch=lambda s, i, n: frames[s])
    assert not tiny.step()["positions"]                         # 2 USDT can never meet the 5 USDT minimum


def test_sweep_summary():
    from binance_team.sweep import run_sweep
    dfs = {s: synthetic(2500, seed=i) for i, s in enumerate(["BTCUSDT", "ETHUSDT"])}
    rows, m = run_sweep(dfs, grid=dict(risk=[0.01, 0.03], lead_threshold=[0.3], stop_atr=[2.5]))
    assert len(rows) == 2 == m["configs"]
    assert 0 <= m["share_positive"] <= 1 and m["dd_worst"] <= m["dd_median"] <= 0


def test_top_symbols_filters_stables_and_illiquid(monkeypatch):
    t = [{"symbol": "BTCUSDT", "quoteVolume": "9e9"}, {"symbol": "USDCUSDT", "quoteVolume": "8e9"},
         {"symbol": "ETHUSDT", "quoteVolume": "5e9"}, {"symbol": "TINYUSDT", "quoteVolume": "1e5"},
         {"symbol": "ETHBTC", "quoteVolume": "7e9"}]
    monkeypatch.setattr(data, "_get", lambda path, params: t)
    assert data.top_symbols(10) == ["BTCUSDT", "ETHUSDT"]


def test_scan_and_position_cap():
    from binance_team.scan import scan
    frames = {s: synthetic(600, seed=i) for i, s in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT"])}
    rows = scan(list(frames), fetch=lambda s, itv, n: frames[s])
    assert len(rows) == 3 and all("reason" in r for r in rows)
    assert [r["enter"] for r in rows] == sorted([r["enter"] for r in rows], reverse=True)
    dfs = {s: synthetic(2500, seed=i) for i, s in enumerate(["BTCUSDT", "A", "B", "C", "D"])}
    r = run_backtest(dfs, cash=1000.0, max_positions=2)
    assert r["max_open"] <= 2


def test_rank_modes():
    from binance_team.scan import scan
    frames = {s: synthetic(600, seed=i) for i, s in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT"])}
    f = lambda s, itv, n: frames[s]
    for rk in ("conviction", "per_risk"):
        assert len(scan(list(frames), fetch=f, rank=rk)) == 3
    dfs = {s: synthetic(2500, seed=i) for i, s in enumerate(["BTCUSDT", "A", "B"])}
    for rk in ("conviction", "per_risk"):
        assert run_backtest(dfs, cash=1000.0, rank=rk)["final_cash"] > 0
