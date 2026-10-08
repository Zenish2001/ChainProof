"""
trading/paper_trading.py

Paper trading bot: trades BTC, ETH and SOL with pretend money on live
Coinbase prices, using the same 4-indicator strategy as the backtests.

Rules
  - Signals come from daily candles: RSI, MACD, SMA 20/50 and Bollinger Bands
    each vote BUY, SELL or HOLD. A signal needs `min_votes` matching votes.
  - Each coin gets an equal slice of the account (account value / number of
    coins, capped by available cash).
  - Exits: a SELL signal, a stop-loss, or a take-profit.
  - Fees: `fee_rate` on every buy and sell.
  - After an exit, a coin isn't bought again on the same daily candle.

Warm start
  On first run (empty trade history) the bot replays the last `warm_days`
  days of daily candles through exactly these rules, so the account has a
  history. Those trades and snapshots are stored with source='replay'; every
  trade after that is source='live'. The dashboard labels them separately.
"""

import json
import os
import sys
import threading
import traceback
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.database import TradingDatabase, STATE_DIR  # noqa: E402
from data.price_fetcher import get_spot_price, get_daily_candles  # noqa: E402
from indicators.technical_indicators import TechnicalIndicators  # noqa: E402

PORTFOLIO_FILE = os.path.join(STATE_DIR, "paper_portfolio.json")
VOTE_COLS = ["rsi_signal", "macd_signal", "ma_signal", "bb_signal"]


def _ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class PaperTradingBot:
    def __init__(self, symbols=("BTC-USD", "ETH-USD", "SOL-USD"), initial_capital=10000,
                 stop_loss=0.03, take_profit=0.20, min_votes=2, fee_rate=0.001, warm_days=90,
                 position_size=None):
        self.db = TradingDatabase()
        self.symbols = list(symbols)
        self.initial_capital = float(initial_capital)
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.min_votes = min_votes
        self.min_strength = min_votes * 25  # kept for older callers
        self.fee_rate = fee_rate
        self.warm_days = warm_days
        # Share of the account one coin may use. Default: an equal slice.
        self.position_size = position_size or 1.0 / len(self.symbols)

        self.portfolio = {"cash": self.initial_capital, "positions": {}, "total_value": self.initial_capital,
                          "total_profit_loss": 0.0, "fees_paid": 0.0, "live_since": None,
                          "live_start_value": None, "live_start_prices": {}}
        self.last_exit_day = {}

        self.is_running = False
        self.check_interval = 3600
        self._stop_event = threading.Event()
        self.last_signals = {}
        self.last_cycle_time = None
        self.last_error = None

        self.load_portfolio()

    # ------------------------------------------------------------ storage
    def save_portfolio(self):
        data = dict(self.portfolio)
        data["positions"] = {s: {**p, "entry_date": p["entry_date"].isoformat()
                                 if isinstance(p.get("entry_date"), datetime) else p.get("entry_date")}
                             for s, p in self.portfolio["positions"].items()}
        data["last_exit_day"] = self.last_exit_day
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load_portfolio(self):
        try:
            with open(PORTFOLIO_FILE) as f:
                saved = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        self.last_exit_day = saved.pop("last_exit_day", {})
        for p in saved.get("positions", {}).values():
            if isinstance(p.get("entry_date"), str):
                p["entry_date"] = datetime.fromisoformat(p["entry_date"])
        self.portfolio.update(saved)

    # --------------------------------------------------------------- data
    def fetch_current_price(self, symbol):
        return get_spot_price(symbol)

    def get_historical_data(self, symbol, days=300):
        latest = self.db.latest_candle_time(symbol)
        if latest is None or datetime.utcnow() - latest.to_pydatetime() > timedelta(hours=20):
            fresh = get_daily_candles(symbol, days=max(days, 300))
            if not fresh.empty:
                self.db.insert_price_data(symbol, fresh)
        return self.db.get_price_data(symbol)

    @staticmethod
    def _votes(row):
        return [row[c] for c in VOTE_COLS]

    def generate_signal(self, symbol):
        """Latest signal for a symbol: (signal, strength, details)."""
        df = self.get_historical_data(symbol)
        if df.empty or len(df) < 50:
            return "HOLD", 0, {}
        signals, ind = TechnicalIndicators.generate_signals(df)
        last, row = signals.iloc[-1], ind.iloc[-1]

        def num(x):
            return None if x != x else round(float(x), 2)

        band = row["bb_upper"] - row["bb_lower"]
        details = {
            "candle_date": str(ind.index[-1])[:10],
            "votes": {
                "RSI (14)": {"vote": last["rsi_signal"], "value": num(row["rsi"]),
                             "rule": "Buy under 30, sell over 70"},
                "MACD (12, 26, 9)": {"vote": last["macd_signal"], "value": num(row["macd"] - row["macd_signal"]),
                                     "rule": "Buy when MACD is above its signal line"},
                "SMA 20 vs 50": {"vote": last["ma_signal"], "value": num(row["sma_20"] - row["sma_50"]),
                                 "rule": "Buy when the 20-day average is above the 50-day"},
                "Bollinger %B (20, 2)": {"vote": last["bb_signal"],
                                         "value": num((row["close"] - row["bb_lower"]) / band * 100) if band else None,
                                         "rule": "Buy below the lower band (%B under 0), sell above the upper (over 100)"},
            },
        }
        return last["overall_signal"], float(last["signal_strength"]), details

    # ------------------------------------------------------------- orders
    def account_value(self, prices):
        value = self.portfolio["cash"]
        for s, p in self.portfolio["positions"].items():
            value += p["quantity"] * (prices.get(s) or p["entry_price"])
        return value

    def execute_buy(self, symbol, price, signal_strength, prices=None, when=None, source="live", votes=""):
        if symbol in self.portfolio["positions"]:
            return False
        budget = self.account_value(prices or {symbol: price}) * self.position_size
        investment = min(budget, self.portfolio["cash"])
        if investment < 10:  # nothing meaningful left to invest
            return False
        fee = investment * self.fee_rate
        quantity = (investment - fee) / price
        when = when or datetime.utcnow()
        self.portfolio["positions"][symbol] = {"quantity": quantity, "entry_price": price, "entry_date": when,
                                               "cost": investment}
        self.portfolio["cash"] -= investment
        self.portfolio["fees_paid"] = self.portfolio.get("fees_paid", 0) + fee
        self.db.insert_trade(symbol, "BUY", quantity, price, strategy="paper_trading", fees=fee, timestamp=_ts(when),
                             source=source, notes=f"Signal {signal_strength:.0f}%{(' (' + votes + ')') if votes else ''}")
        return True

    def execute_sell(self, symbol, price, reason="SIGNAL", signal_strength=0, when=None, source="live"):
        if symbol not in self.portfolio["positions"]:
            return False
        pos = self.portfolio["positions"].pop(symbol)
        gross = pos["quantity"] * price
        fee = gross * self.fee_rate
        proceeds = gross - fee
        cost = pos.get("cost", pos["quantity"] * pos["entry_price"])
        pnl = proceeds - cost
        pnl_pct = pnl / cost * 100 if cost else 0
        when = when or datetime.utcnow()
        self.portfolio["cash"] += proceeds
        self.portfolio["total_profit_loss"] = self.portfolio.get("total_profit_loss", 0) + pnl
        self.portfolio["fees_paid"] = self.portfolio.get("fees_paid", 0) + fee
        self.last_exit_day[symbol] = when.strftime("%Y-%m-%d")
        held = max(0, (when - pos["entry_date"]).days)
        label = {"SIGNAL": "Sell signal", "STOP_LOSS": "Stop-loss", "TAKE_PROFIT": "Take-profit"}.get(reason, reason)
        self.db.insert_trade(symbol, "SELL", pos["quantity"], price, strategy="paper_trading", fees=fee,
                             timestamp=_ts(when), source=source, pnl=pnl, pnl_pct=pnl_pct,
                             notes=f"{label}, held {held} day{'' if held == 1 else 's'}")
        return True

    def _exit_check(self, symbol, low, high, when, source):
        """Stop-loss / take-profit against a price range. Returns the action or None."""
        pos = self.portfolio["positions"].get(symbol)
        if not pos:
            return None
        stop = pos["entry_price"] * (1 - self.stop_loss)
        target = pos["entry_price"] * (1 + self.take_profit)
        if low <= stop:
            self.execute_sell(symbol, stop, reason="STOP_LOSS", when=when, source=source)
            return "STOP_LOSS"
        if high >= target:
            self.execute_sell(symbol, target, reason="TAKE_PROFIT", when=when, source=source)
            return "TAKE_PROFIT"
        return None

    def _act_on_signal(self, symbol, price, signal, votes, prices, when, source, day):
        """Entry/exit on the indicator signal. Returns the action taken."""
        agree = max(votes.count("BUY"), votes.count("SELL"))
        vote_text = f"{votes.count('BUY')} buy, {votes.count('SELL')} sell, {votes.count('HOLD')} hold"
        holding = symbol in self.portfolio["positions"]
        if signal == "SELL" and agree >= self.min_votes and holding:
            self.execute_sell(symbol, price, reason="SIGNAL", signal_strength=agree * 25, when=when, source=source)
            return "SELL"
        if signal == "BUY" and agree >= self.min_votes and not holding:
            if self.last_exit_day.get(symbol) == day:
                return "WAIT"  # exited earlier on this candle; don't flip back in
            if self.execute_buy(symbol, price, agree * 25, prices=prices, when=when, source=source, votes=vote_text):
                return "BUY"
            return "NO_CASH"
        return "IN_POSITION" if holding else "HOLD"

    # ---------------------------------------------------------- warm start
    def warm_start(self):
        """Replay the last `warm_days` daily candles through the rules, once."""
        if self.db.count_trades() > 0 or self.portfolio.get("live_since"):
            return
        frames = {}
        for s in self.symbols:
            df = self.get_historical_data(s)
            if len(df) >= 60:
                sig, _ = TechnicalIndicators.generate_signals(df)
                frames[s] = (df, sig)
        if not frames:
            return
        # Only completed daily candles: today's candle is still forming.
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        days = sorted(d for d in set().union(*[set(df.index) for df, _ in frames.values()])
                      if d.to_pydatetime() < today)[-self.warm_days:]
        for day in days:
            when = day.to_pydatetime().replace(hour=23, minute=59)
            dkey = when.strftime("%Y-%m-%d")
            closes = {s: float(df.loc[day, "close"]) for s, (df, _) in frames.items() if day in df.index}
            for s, (df, sig) in frames.items():
                if day not in df.index:
                    continue
                row, srow = df.loc[day], sig.loc[day]
                votes = self._votes(srow)
                action = self._exit_check(s, float(row["low"]), float(row["high"]), when, "replay")
                if not action:
                    action = self._act_on_signal(s, float(row["close"]), srow["overall_signal"], votes,
                                                 closes, when, "replay", dkey)
                if action not in ("HOLD", "IN_POSITION"):
                    self.db.insert_decision(s, float(row["close"]), srow["overall_signal"], votes, action,
                                            source="replay", timestamp=_ts(when))
            self.db.record_snapshot(self.account_value(closes), self.portfolio["cash"], self.initial_capital,
                                    timestamp=_ts(when), source="replay")
        self.save_portfolio()

    # ---------------------------------------------------------- live loop
    def run_trading_cycle(self):
        now = datetime.utcnow()
        self.last_cycle_time = datetime.now()
        prices = {s: self.fetch_current_price(s) for s in self.symbols}
        prices = {s: p for s, p in prices.items() if p}

        if self.portfolio.get("live_since") is None and prices:
            self.portfolio["live_since"] = _ts(now)
            self.portfolio["live_start_value"] = self.account_value(prices)
            self.portfolio["live_start_prices"] = dict(prices)

        for s in self.symbols:
            try:
                price = prices.get(s)
                if not price:
                    continue
                signal, strength, details = self.generate_signal(s)
                votes = [v["vote"] for v in details.get("votes", {}).values()]
                action = self._exit_check(s, price, price, now, "live")
                if not action and votes:
                    action = self._act_on_signal(s, price, signal, votes, prices, now, "live",
                                                 details.get("candle_date"))
                action = action or "HOLD"
                self.db.insert_decision(s, price, signal, votes or ["HOLD"] * 4, action, source="live")
                self.last_signals[s] = {"signal": signal, "strength": float(strength), "price": float(price),
                                        "timestamp": datetime.now().isoformat(), "action": action, **details}
            except Exception as e:
                self.last_error = f"{s}: {e}"
                traceback.print_exc()

        self.portfolio["total_value"] = self.account_value(prices)
        self.db.set_positions(self.portfolio["positions"], prices)
        self.db.record_snapshot(self.portfolio["total_value"], self.portfolio["cash"], self.initial_capital)
        self.save_portfolio()

    def start(self):
        self.is_running = True
        self._stop_event.clear()
        try:
            self.warm_start()
        except Exception as e:
            self.last_error = f"warm start: {e}"
            traceback.print_exc()
        try:
            while self.is_running:
                try:
                    self.run_trading_cycle()
                    self.last_error = None
                except Exception as e:
                    self.last_error = str(e)
                    traceback.print_exc()
                if self._stop_event.wait(self.check_interval):
                    break
        finally:
            self.is_running = False
            self.save_portfolio()

    def stop(self):
        self.is_running = False
        self._stop_event.set()


if __name__ == "__main__":
    bot = PaperTradingBot()
    bot.check_interval = int(os.environ.get("CHECK_INTERVAL", "300"))
    print(f"Paper trading {', '.join(bot.symbols)} every {bot.check_interval // 60} min. Ctrl+C to stop.")
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()
