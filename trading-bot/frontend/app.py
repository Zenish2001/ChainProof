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

from flask import Flask, abort, jsonify, render_template

sys.path.append(str(Path(__file__).resolve().parent.parent))

from data.database import TradingDatabase  # noqa: E402
from trading.paper_trading import PaperTradingBot  # noqa: E402

AUTOSTART = os.environ.get("AUTOSTART", "1") == "1"
ALLOW_CONTROL = os.environ.get("ALLOW_CONTROL", "0") == "1"
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))
SYMBOLS = ["BTC-USD"]
INITIAL_CAPITAL = 10_000.0
CHAINPROOF_URL = os.environ.get("CHAINPROOF_URL", "https://github.com/Zenish2001/ChainProof")
REPO_URL = "https://github.com/Zenish2001/ChainProof/tree/main/trading-bot"

app = Flask(__name__)
app.json.sort_keys = False  # keep indicator order as written
db = TradingDatabase()

bot = PaperTradingBot(symbols=SYMBOLS, initial_capital=INITIAL_CAPITAL)
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
    )


@app.route("/api/state")
def state():
    running = bool(bot_thread and bot_thread.is_alive() and bot.is_running)
    next_check_in = None
    if running and bot.last_cycle_time:
        elapsed = (datetime.now() - bot.last_cycle_time).total_seconds()
        next_check_in = max(0, round(bot.check_interval - elapsed))

    # Open positions, valued at the price from the latest cycle.
    last_prices = {s: v.get("price") for s, v in bot.last_signals.items()}
    positions = []
    for symbol, p in bot.portfolio.get("positions", {}).items():
        price = last_prices.get(symbol) or p["entry_price"]
        value = p["quantity"] * price
        cost = p["quantity"] * p["entry_price"]
        entry = p.get("entry_date")
        positions.append({
            "symbol": symbol,
            "quantity": p["quantity"],
            "entry_price": p["entry_price"],
            "entry_date": entry.isoformat() if hasattr(entry, "isoformat") else entry,
            "price": price,
            "value": value,
            "unrealized": value - cost,
            "unrealized_pct": (price / p["entry_price"] - 1) * 100,
            "stop_price": p["entry_price"] * (1 - bot.stop_loss),
            "target_price": p["entry_price"] * (1 + bot.take_profit),
        })

    cash = float(bot.portfolio.get("cash", INITIAL_CAPITAL))
    total = cash + sum(p["value"] for p in positions)

    candles = {}
    for symbol in SYMBOLS:
        df = db.get_price_data(symbol, limit=120)
        candles[symbol] = [{"t": str(ts)[:10], "close": round(float(c), 2)} for ts, c in df["close"].items()]

    return jsonify({
        "running": running,
        "allow_control": ALLOW_CONTROL,
        "started_at": started_at.isoformat() if started_at else None,
        "last_cycle": bot.last_cycle_time.isoformat() if bot.last_cycle_time else None,
        "next_check_in": next_check_in,
        "check_interval": bot.check_interval,
        "last_error": bot.last_error,
        "rules": {
            "position_size_pct": bot.position_size * 100,
            "stop_loss_pct": bot.stop_loss * 100,
            "take_profit_pct": bot.take_profit * 100,
            "votes_needed": round(bot.min_strength / 25),
        },
        "account": {
            "initial": INITIAL_CAPITAL,
            "cash": cash,
            "total": total,
            "return_pct": (total / INITIAL_CAPITAL - 1) * 100,
            "realized_pnl": float(bot.portfolio.get("total_profit_loss", 0)),
        },
        "positions": positions,
        "signals": bot.last_signals,
        "trades": db.get_trades(limit=50),
        "equity": db.get_snapshots(limit=500),
        "candles": candles,
        "server_time": datetime.now().isoformat(),
    })


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
