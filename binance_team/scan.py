"""Market scanner: asks the whole team about many coins and ranks what it would buy today.
This ranks setups by the team's rules. It does NOT predict the future."""
from .agents import LeadAgent, build_features, opinions
from .data import fetch_klines


def scan(symbols, fetch=fetch_klines, interval="1d", stop_atr=2.5, rank="conviction"):
    mrow = build_features(fetch("BTCUSDT", interval, 400)).iloc[-2].to_dict()
    lead, rows = LeadAgent(), []
    for s in symbols:
        try:
            df = fetch(s, interval, 400)
            f = build_features(df)
            row = f.iloc[-2]
            d = lead.decide(opinions(row.to_dict(), mrow))
            price = float(df["close"].iloc[-1])
            atr = float(row["atr"])
            rows.append(dict(symbol=s, enter=d.enter, score=d.score, size=d.size, reason=d.reason,
                             price=price, stop=price - stop_atr * atr, risk_pct=stop_atr * atr / price,
                             r30=float(df["close"].iloc[-1] / df["close"].iloc[-31] - 1),
                             r90=float(df["close"].iloc[-1] / df["close"].iloc[-91] - 1),
                             dollar_vol=float(row["dollar_vol"]),
                             per_risk=d.score / (stop_atr * atr / price) if atr > 0 else 0.0))
        except Exception as e:
            rows.append(dict(symbol=s, enter=False, score=0.0, size=0.0, reason=f"error: {e}",
                             price=0, stop=0, risk_pct=0, r30=0, r90=0, dollar_vol=0, per_risk=0.0))
    k = "score" if rank == "conviction" else "per_risk"
    rows.sort(key=lambda x: (-x["enter"], -x[k]))
    return rows
