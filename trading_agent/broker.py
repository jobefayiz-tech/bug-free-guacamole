import os


class PaperBroker:
    """Simulated account. No real money."""

    def __init__(self, cash=10_000.0, fee_rate=0.001):
        self.cash, self.qty, self.fee = cash, 0.0, fee_rate

    def equity(self, price):
        return self.cash + self.qty * price

    def buy(self, symbol, qty, price):
        self.cash -= qty * price * (1 + self.fee)
        self.qty += qty
        return price

    def sell(self, symbol, qty, price):
        self.cash += qty * price * (1 - self.fee)
        self.qty -= qty
        return price


class CcxtBroker:
    """Real orders on any ccxt exchange. Requires LIVE_TRADING=yes and API keys in env
    (<EXCHANGE>_API_KEY / <EXCHANGE>_SECRET). Use keys with withdrawals DISABLED."""

    def __init__(self, exchange_id, quote="USDT"):
        import ccxt
        if os.environ.get("LIVE_TRADING") != "yes":
            raise RuntimeError("Set LIVE_TRADING=yes to enable real orders.")
        p = exchange_id.upper()
        self.ex = getattr(ccxt, exchange_id)({
            "apiKey": os.environ[f"{p}_API_KEY"], "secret": os.environ[f"{p}_SECRET"],
            "enableRateLimit": True})
        self.quote = quote

    def equity(self, price):
        bal = self.ex.fetch_balance()
        return float(bal["total"].get(self.quote, 0.0))

    def buy(self, symbol, qty, price):
        o = self.ex.create_market_buy_order(symbol, self.ex.amount_to_precision(symbol, qty))
        return float(o.get("average") or price)

    def sell(self, symbol, qty, price):
        o = self.ex.create_market_sell_order(symbol, self.ex.amount_to_precision(symbol, qty))
        return float(o.get("average") or price)
