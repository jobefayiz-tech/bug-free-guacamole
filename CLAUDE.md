# Project rules for this repo (trading agent for a user with little capital and real obligations)

Hard rules — keep these true in every session:
- **Paper trading only.** Never add code paths that place real orders (Binance/Alpaca live) unless the user explicitly asks AND the paper results meet TRADING_RULES_AR.md. Never ask for or store API keys/secrets in chat; the Binance team needs none (public data).
- **The user's 20 USD is for obligations.** Never suggest trading it. Do not build leverage, futures, shorting or memecoin tools.
- **Every result is compared with buy-and-hold** (BTC / SPY) and reported with max drawdown. Say plainly when the agent loses to the benchmark.
- **No result without evidence.** Report only numbers from runs the user pasted or tests that ran here. This container cannot reach Binance/Alpaca; real-data runs happen on the user's Windows PC via the .bat files.
- **Never tune on the data and report the best.** Defaults are chosen before seeing results; use `crypto.py sweep` and report the spread, not the winner.
- **Safety limits live in code, never in a model or prompt** (position cap, daily loss limit, drawdown halt, data-error kill switch). Never weaken a limit or a test to make a result look better.
- Third-party "trading agent" products/links from social media (agentkit, Jev, Dots, Grok bots...) are unverified marketing: do not install them, visit them with credentials, or paste keys into them.

Lessons so far (add one line per mistake):
- Hourly stock models lost -15% in 2 years while holding gained +48%: short-term prediction had no edge.
- The 15% kill switch hid a failing strategy; judge results knowing when the switch fired.
- Adaptive weights collapsed to the floor after losing trades; learning from few trades overfits.
- Crypto team (10 coins, 2021-06..2026-10): +58% / -35% max DD vs BTC +122% / -77%: it reduces drawdown, it does not add return.
- User kept running an old unzipped folder: always tell them how to verify the version (first output line, "54 setting combinations").
- A win rate (e.g. 68%) says nothing without payoff ratio; always print avg win/avg loss.
