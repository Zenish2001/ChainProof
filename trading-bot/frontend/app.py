"""
frontend/app.py

Dashboard for the paper trading bot.

The bot runs in a background thread inside this process and trades with
pretend money ($10,000 to start). The page reads everything from one
endpoint, /api/state.

Environment variables:
  AUTOSTART=1          start the bot when the server starts (default 1)
  ALLOW_CONTROL=0      show Start/Stop buttons and accept /api/bot/* calls.
                       Keep this off on a public server so visitors can't
                       stop the bot.
  CHECK_INTERVAL=300   seconds between trading cycles
  STATE_DIR=...        where the SQLite file and portfolio JSON are kept

Run locally from trading-bot/:
    python frontend/app.py          -> http://localhost:5001
"""

import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import time  # noqa: E402

from flask import Flask, abort, jsonify, render_template, request

sys.path.append(str(Path(__file__).resolve().parent.parent))

from data.database import TradingDatabase  # noqa: E402
from data import price_fetcher  # noqa: E402
from indicators.technical_indicators import TechnicalIndicators  # noqa: E402
from strategies.trading_strategy import TradingStrategy  # noqa: E402
from trading.paper_trading import PaperTradingBot  # noqa: E402

AUTOSTART = os.environ.get("AUTOSTART", "1") == "1"
ALLOW_CONTROL = os.environ.get("ALLOW_CONTROL", "0") == "1"
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))
MARKETS = ["BTC-USD", "ETH-USD", "SOL-USD"]
SYMBOLS = MARKETS  # the bot trades all three
CHAINPROOF_CONTRACT = "0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955"
ETHERSCAN_URL = f"https://sepolia.etherscan.io/address/{CHAINPROOF_CONTRACT}"
INITIAL_CAPITAL = 10_000.0
CHAINPROOF_URL = os.environ.get("CHAINPROOF_URL", "https://github.com/Zenish2001/ChainProof")
REPO_URL = "https://github.com/Zenish2001/ChainProof/tree/main/trading-bot"

app = Flask(__name__)
app.json.sort_keys = False  # keep indicator order as written
db = TradingDatabase()

bot = PaperTradingBot(symbols=SYMBOLS, initial_capital=INITIAL_CAPITAL,
                      warm_days=int(os.environ.get("WARM_START_DAYS", "90")))
bot.check_interval = CHECK_INTERVAL
bot_thread = None
_lock = threading.Lock()
started_at = None


def start_bot():
    global bot_thread, started_at
    with _lock:
        if bot_thread and bot_thread.is_alive():
            return False
        bot_thread = threading.Thread(target=bot.start, name="paper-bot", daemon=True)
        bot_thread.start()
        started_at = datetime.now()
        return True


def stop_bot():
    with _lock:
        if not (bot_thread and bot_thread.is_alive()):
            return False
        bot.stop()
        return True


if AUTOSTART:
    start_bot()


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        allow_control=ALLOW_CONTROL,
        chainproof_url=CHAINPROOF_URL,
        repo_url=REPO_URL,
        etherscan_url=ETHERSCAN_URL,
    )


@app.route("/api/state")
def state():
    running = bool(bot_thread and bot_thread.is_alive() and bot.is_running)
    next_check_in = None
    if running and bot.last_cycle_time:
        elapsed = (datetime.now() - bot.last_cycle_time).total_seconds()
        next_check_in = max(0, round(bot.check_interval - elapsed))

    # Open positions, valued at the price from the latest cycle.
    last_prices = {sym: v.get("price") for sym, v in bot.last_signals.items()}
    now = datetime.utcnow()
    positions = []
    for symbol, p in bot.portfolio.get("positions", {}).items():
        price = last_prices.get(symbol) or p["entry_price"]
        value = p["quantity"] * price
        cost = p.get("cost", p["quantity"] * p["entry_price"])
        entry = p.get("entry_date")
        positions.append({
            "symbol": symbol,
            "quantity": p["quantity"],
            "entry_price": p["entry_price"],
            "entry_date": entry.isoformat() if hasattr(entry, "isoformat") else entry,
            "held_days": (now - entry).days if hasattr(entry, "year") else None,
            "price": price,
            "value": value,
            "unrealized": value - cost,
            "unrealized_pct": (value / cost - 1) * 100 if cost else 0,
            "stop_price": p["entry_price"] * (1 - bot.stop_loss),
            "target_price": p["entry_price"] * (1 + bot.take_profit),
        })

    cash = float(bot.portfolio.get("cash", INITIAL_CAPITAL))
    total = cash + sum(p["value"] for p in positions)

    # Live-only performance: since the replay ended and live trading began.
    live = None
    if bot.portfolio.get("live_since") and bot.portfolio.get("live_start_value"):
        start_val = bot.portfolio["live_start_value"]
        sp = bot.portfolio.get("live_start_prices") or {}
        hold = [last_prices[s_] / sp[s_] for s_ in sp if last_prices.get(s_) and sp.get(s_)]
        live = {
            "since": bot.portfolio["live_since"],
            "start_value": start_val,
            "return_pct": (total / start_val - 1) * 100,
            "buy_hold_pct": (sum(hold) / len(hold) - 1) * 100 if hold else None,
        }

    stats = db.trade_stats()
    closed = stats.get("n") or 0

    return jsonify({
        "running": running,
        "allow_control": ALLOW_CONTROL,
        "started_at": started_at.isoformat() if started_at else None,
        "last_cycle": bot.last_cycle_time.isoformat() if bot.last_cycle_time else None,
        "next_check_in": next_check_in,
        "check_interval": bot.check_interval,
        "last_error": bot.last_error,
        "symbols": SYMBOLS,
        "rules": {
            "allocation_pct": bot.position_size * 100,
            "stop_loss_pct": bot.stop_loss * 100,
            "take_profit_pct": bot.take_profit * 100,
            "votes_needed": bot.min_votes,
            "fee_pct": bot.fee_rate * 100,
            "warm_days": bot.warm_days,
        },
        "account": {
            "initial": INITIAL_CAPITAL,
            "cash": cash,
            "total": total,
            "return_pct": (total / INITIAL_CAPITAL - 1) * 100,
            "realized_pnl": float(bot.portfolio.get("total_profit_loss", 0)),
            "fees_paid": float(bot.portfolio.get("fees_paid", 0)),
            "closed_trades": closed,
            "win_rate": (stats["wins"] or 0) / closed * 100 if closed else None,
            "avg_trade_pct": stats.get("avg_pct"),
            "best_trade_pct": stats.get("best"),
            "worst_trade_pct": stats.get("worst"),
        },
        "live": live,
        "positions": positions,
        "signals": bot.last_signals,
        "trades": db.get_trades(limit=60),
        "decisions": db.get_decisions(limit=40),
        "equity": db.get_snapshots(limit=600),
        "server_time": datetime.now().isoformat(),
    })


_price_cache = {"t": 0, "data": {}, "error": None}


@app.route("/api/prices")
def prices():
    """Live BTC/ETH/SOL prices with 24h change, cached for 20 seconds so
    page refreshes don't hammer the APIs. Falls back to the last good
    values (marked stale) if every source fails."""
    if time.time() - _price_cache["t"] > 20:
        data = price_fetcher.get_market_snapshot(MARKETS)
        if data:
            _price_cache.update(t=time.time(), data=data, error=None)
        else:
            _price_cache["error"] = "Couldn't reach Coinbase or CoinGecko from the server."
            _price_cache["t"] = time.time() - 15  # retry again in ~5 seconds
    return jsonify({"prices": _price_cache["data"], "error": _price_cache.get("error"),
                    "age_seconds": round(time.time() - _price_cache["t"]) if _price_cache["data"] else None})


def candles_for(symbol):
    """Daily candles from the local store, refreshed from Coinbase when stale."""
    latest = db.latest_candle_time(symbol)
    if latest is None or (datetime.utcnow() - latest.to_pydatetime()).total_seconds() > 20 * 3600:
        fresh = price_fetcher.get_daily_candles(symbol, days=300)
        if not fresh.empty:
            db.insert_price_data(symbol, fresh)
    return db.get_price_data(symbol)


def _f(x, nd=2):
    return None if x is None or x != x else round(float(x), nd)


@app.route("/api/market/<symbol>")
def market(symbol):
    if symbol not in MARKETS:
        abort(404)
    df = candles_for(symbol)
    if len(df) < 50:
        return jsonify({"symbol": symbol, "candles": [], "signals": []})
    signals, ind = TechnicalIndicators.generate_signals(df)
    ind = ind.tail(150)
    signals = signals.tail(150)
    candles = [{
        "t": str(ts)[:10],
        "o": _f(r["open"]), "h": _f(r["high"]), "l": _f(r["low"]), "c": _f(r["close"]),
        "sma20": _f(r["sma_20"]), "sma50": _f(r["sma_50"]),
        "bbu": _f(r["bb_upper"]), "bbl": _f(r["bb_lower"]),
        "rsi": _f(r["rsi"]), "macd": _f(r["macd"], 4), "macds": _f(r["macd_signal"], 4), "macdh": _f(r["macd_hist"], 4),
    } for ts, r in ind.iterrows()]
    recent = [{
        "t": str(ts)[:10], "price": _f(r["price"]),
        "rsi": r["rsi_signal"], "macd": r["macd_signal"], "ma": r["ma_signal"], "bb": r["bb_signal"],
        "overall": r["overall_signal"], "strength": _f(r["signal_strength"], 0),
    } for ts, r in signals.tail(10).iloc[::-1].iterrows()]
    return jsonify({"symbol": symbol, "candles": candles, "signals": recent})


# ---------------------------------------------------------------- backtest
_bt_lock = threading.Lock()
_bt_cache = {}


@app.route("/api/backtest", methods=["POST"])
def backtest():
    """Run the strategy over the stored daily candles with the visitor's
    settings. Inputs are clamped, results are cached per setting."""
    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", "BTC-USD")
    if symbol not in MARKETS:
        abort(400)
    clamp = lambda v, lo, hi, d: min(hi, max(lo, float(v if v is not None else d)))  # noqa: E731
    size = clamp(body.get("position_size"), 0.1, 1.0, 0.95)
    sl = clamp(body.get("stop_loss"), 0.01, 0.30, 0.03)
    tp = clamp(body.get("take_profit"), 0.02, 1.00, 0.20)
    key = (symbol, round(size, 3), round(sl, 3), round(tp, 3), str(db.latest_candle_time(symbol)))
    if key in _bt_cache:
        return jsonify(_bt_cache[key])

    with _bt_lock:
        df = candles_for(symbol)
        if len(df) < 60:
            return jsonify({"error": "Not enough price history yet."}), 503
        strategy = TradingStrategy(initial_capital=INITIAL_CAPITAL, position_size=size, stop_loss=sl, take_profit=tp)
        trades_df, portfolio_df, perf = strategy.execute_backtest(df, symbol)

    closes = df["close"].reindex(portfolio_df["date"]).to_numpy()
    hold = INITIAL_CAPITAL * closes / closes[0]
    equity = [{"t": str(d)[:10], "v": round(float(v), 2), "hold": round(float(h), 2)}
              for d, v, h in zip(portfolio_df["date"], portfolio_df["portfolio_value"], hold)]
    trades = [] if trades_df.empty else [{
        "entry": str(r["entry_date"])[:10], "exit": str(r["exit_date"])[:10],
        "entry_price": _f(r["entry_price"]), "exit_price": _f(r["exit_price"]),
        "pnl": _f(r["profit_loss"]), "pnl_pct": _f(r["profit_loss_pct"]),
        "reason": str(r["exit_reason"]),
    } for _, r in trades_df.iterrows()]
    result = {
        "symbol": symbol,
        "settings": {"position_size": size, "stop_loss": sl, "take_profit": tp},
        "period": [equity[0]["t"], equity[-1]["t"]] if equity else None,
        "metrics": {k: _f(perf.get(k)) for k in
                    ["total_return_pct", "total_trades", "win_rate", "sharpe_ratio", "max_drawdown", "final_portfolio_value"]},
        "buy_hold_pct": _f((hold[-1] / INITIAL_CAPITAL - 1) * 100) if len(hold) else None,
        "equity": equity,
        "trades": trades[-20:],
    }
    if len(_bt_cache) > 200:
        _bt_cache.clear()
    _bt_cache[key] = result
    return jsonify(result)


@app.route("/api/bot/start", methods=["POST"])
def api_start():
    if not ALLOW_CONTROL:
        abort(403)
    return jsonify({"started": start_bot()})


@app.route("/api/bot/stop", methods=["POST"])
def api_stop():
    if not ALLOW_CONTROL:
        abort(403)
    return jsonify({"stopped": stop_bot()})


@app.route("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    print("Paper trading dashboard at http://localhost:5001")
    app.run(port=5001, debug=False, use_reloader=False)
