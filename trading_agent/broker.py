import os


class PaperBroker:
    """Simulated account. No real money."""

    def __init__(self, cash=10_000.0, fee_rate=0.001):
        self.cash, self.holdings, self.marks, self.fee = cash, {}, {}, fee_rate

    def mark(self, symbol, price):
        self.marks[symbol] = price

    def equity(self, price=None):
        return self.cash + sum(q * self.marks.get(s, 0.0) for s, q in self.holdings.items())

    def buying_power(self):
        return self.cash

    def position_qty(self, symbol):
        return self.holdings.get(symbol, 0.0)

    def normalize_qty(self, qty):
        return qty

    def is_open(self):
        return True

    def buy(self, symbol, qty, price):
        self.cash -= qty * price * (1 + self.fee)
        self.holdings[symbol] = self.holdings.get(symbol, 0.0) + qty
        return price

    def sell(self, symbol, qty, price):
        self.cash += qty * price * (1 - self.fee)
        self.holdings[symbol] = self.holdings.get(symbol, 0.0) - qty
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

    marks = None

    def mark(self, symbol, price):
        self.marks = self.marks or {}
        self.marks[symbol] = price

    def is_open(self):
        return True

    def normalize_qty(self, qty):
        return qty

    def position_qty(self, symbol):
        return None  # unknown; agent-side monitoring only

    def equity(self, price=None):
        total = self.ex.fetch_balance()["total"]
        eq = float(total.get(self.quote, 0.0))
        for sym, px in (self.marks or {}).items():  # add value of held coins
            eq += float(total.get(sym.split("/")[0], 0.0)) * px
        return eq

    def buying_power(self):
        return float(self.ex.fetch_balance()["free"].get(self.quote, 0.0))

    def buy(self, symbol, qty, price):
        o = self.ex.create_market_buy_order(symbol, self.ex.amount_to_precision(symbol, qty))
        return float(o.get("average") or price)

    def sell(self, symbol, qty, price):
        o = self.ex.create_market_sell_order(symbol, self.ex.amount_to_precision(symbol, qty))
        return float(o.get("average") or price)


class AlpacaBroker:
    """US stocks via Alpaca. Uses Alpaca's PAPER account unless LIVE_TRADING=yes.
    Entries are bracket orders, so the stop-loss and take-profit live on the broker's
    servers and protect the position even if this program stops."""

    supports_bracket = True

    def __init__(self):
        self.live = os.environ.get("LIVE_TRADING") == "yes"
        self.base = "https://api.alpaca.markets" if self.live else "https://paper-api.alpaca.markets"
        from .data import _alpaca_headers
        self.h = _alpaca_headers()

    def _req(self, method, path, **kw):
        import requests
        r = requests.request(method, self.base + path, headers=self.h, timeout=20, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def is_open(self):
        return bool(self._req("GET", "/v2/clock")["is_open"])

    def normalize_qty(self, qty):
        return float(int(qty))  # whole shares (required for bracket orders)

    def mark(self, symbol, price):
        pass

    def equity(self, price=None):
        return float(self._req("GET", "/v2/account")["equity"])

    def buying_power(self):
        return float(self._req("GET", "/v2/account")["buying_power"])

    def position_qty(self, symbol):
        try:
            return float(self._req("GET", f"/v2/positions/{symbol}")["qty"])
        except Exception:
            return 0.0

    def buy(self, symbol, qty, price, stop=None, tp=None):
        body = {"symbol": symbol, "qty": str(int(qty)), "side": "buy",
                "type": "market", "time_in_force": "day"}
        if stop and tp:
            body.update(order_class="bracket",
                        stop_loss={"stop_price": f"{stop:.2f}"},
                        take_profit={"limit_price": f"{tp:.2f}"})
        self._req("POST", "/v2/orders", json=body)
        return price

    def _open_orders(self, symbol):
        return self._req("GET", "/v2/orders",
                         params={"status": "open", "symbols": symbol, "nested": "true"}) or []

    def update_stop(self, symbol, stop):
        for o in self._open_orders(symbol):
            for leg in [o] + (o.get("legs") or []):
                if leg.get("type") in ("stop", "stop_limit"):
                    self._req("PATCH", f"/v2/orders/{leg['id']}",
                              json={"stop_price": f"{stop:.2f}"})

    def sell(self, symbol, qty, price):
        for o in self._open_orders(symbol):
            self._req("DELETE", f"/v2/orders/{o['id']}")
        self._req("POST", "/v2/orders", json={"symbol": symbol, "qty": str(int(qty)),
                  "side": "sell", "type": "market", "time_in_force": "day"})
        return price
