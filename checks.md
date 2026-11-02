# checks.md — what must be true before saying "done" (step | check | pass/fail | evidence)

| step | check | status |
|---|---|---|
| tests | `python -m pytest -q` passes (26+) | run before every push |
| no live orders | grep -rn "create_order\|market_buy\|/v2/orders" binance_team/ crypto.py returns nothing | binance_team is paper-only |
| benchmark | every backtest output prints buy-and-hold next to the team | crypto.py backtest |
| spread | any parameter claim is backed by `crypto.py sweep` (54 settings), not one run | E_crypto_sweep.bat |
| safety | data-error kill switch, daily loss limit, drawdown halt, position cap covered by tests | tests/test_binance_team.py |
| honesty | answer states loss vs benchmark and what was NOT tested | review reply |
