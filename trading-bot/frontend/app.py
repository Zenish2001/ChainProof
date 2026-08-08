from flask import Flask, render_template, jsonify, request
import sys
import threading
from pathlib import Path
from datetime import datetime
import json
import sqlite3

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from trading.paper_trading import PaperTradingBot

app = Flask(__name__)

# Path to database
DB_PATH = 'data/trading_bot.db'

# --- Bot instance + background thread management -----------------------
# The bot itself runs in a daemon thread so its trading-cycle loop doesn't
# block Flask's request handling. check_interval is shortened here for a
# responsive dashboard demo (5 minutes instead of the CLI default of 1 hour)
# — change DASHBOARD_CHECK_INTERVAL below if you want a different cadence.
DASHBOARD_CHECK_INTERVAL = 300  # seconds

paper_bot = None
bot_thread = None


def get_db_connection():
    """Get SQLite database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/portfolio')
def get_portfolio():
    """Get current portfolio data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get latest performance metrics
        cursor.execute("""
            SELECT * FROM performance_metrics 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        latest_metrics = cursor.fetchone()
        
        if latest_metrics:
            total_value = float(latest_metrics['total_portfolio_value'])
            pnl = float(latest_metrics['total_profit_loss'])
            pnl_percent = float(latest_metrics['total_profit_loss_percent'])
            last_update = latest_metrics['timestamp']
        else:
            # Fallback: calculate from portfolio table
            cursor.execute("""
                SELECT * FROM portfolio 
                WHERE quantity > 0
            """)
            holdings = cursor.fetchall()
            
            total_value = 0
            for holding in holdings:
                total_value += float(holding['quantity']) * float(holding['current_price'])
            
            initial_capital = 10000
            if total_value == 0:
                total_value = initial_capital
            
            pnl = total_value - initial_capital
            pnl_percent = (pnl / initial_capital) * 100 if initial_capital > 0 else 0
            last_update = 'Unknown'
        
        # Get current holdings
        cursor.execute("""
            SELECT * FROM portfolio 
            WHERE quantity > 0
            ORDER BY last_updated DESC
        """)
        holdings = cursor.fetchall()
        
        holdings_dict = {}
        invested = 0
        
        for holding in holdings:
            symbol = holding['symbol']
            quantity = float(holding['quantity'])
            current_price = float(holding['current_price'])
            avg_buy_price = float(holding['avg_buy_price'])
            value = quantity * current_price
            cost = quantity * avg_buy_price
            
            invested += cost
            
            holdings_dict[symbol] = {
                'quantity': quantity,
                'current_value': value,
                'cost_basis': cost
            }
        
        # Calculate cash (remaining capital)
        initial_capital = 10000
        cash = max(0, total_value - sum(h['current_value'] for h in holdings_dict.values()))
        
        result = {
            'total_value': round(total_value, 2),
            'cash': round(cash, 2),
            'pnl': round(pnl, 2),
            'pnl_percent': round(pnl_percent, 2),
            'holdings': holdings_dict,
            'last_update': str(last_update)
        }
        
        conn.close()
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in get_portfolio: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'total_value': 10000.00,
            'cash': 10000.00,
            'pnl': 0.00,
            'pnl_percent': 0.00,
            'holdings': {},
            'last_update': 'No data yet'
        })

@app.route('/api/trades')
def get_trades():
    """Get recent trades"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trades 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        trades = cursor.fetchall()
        
        result = [{
            'symbol': trade['symbol'],
            'action': trade['trade_type'].upper() if trade['trade_type'] else 'UNKNOWN',
            'quantity': round(float(trade['quantity']), 6) if trade['quantity'] else 0,
            'price': round(float(trade['price']), 2) if trade['price'] else 0,
            'total': round(float(trade['total_value']), 2) if trade['total_value'] else 0,
            'timestamp': trade['timestamp']
        } for trade in trades]
        
        conn.close()
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in get_trades: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/prices')
def get_prices():
    """Get LIVE prices for BTC, ETH, SOL directly from the Coinbase API
    (via data/price_fetcher.py), with 24h change estimated against the most
    recent price_history row."""
    try:
        from data.price_fetcher import get_all_prices

        conn = get_db_connection()
        cursor = conn.cursor()

        live_prices = get_all_prices()
        prices = {}

        for symbol in ['BTC-USD', 'ETH-USD', 'SOL-USD']:
            live_price = live_prices.get(symbol)

            if live_price is not None:
                cursor.execute("""
                    SELECT close FROM price_history
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (symbol,))
                prior = cursor.fetchone()
                prior_close = float(prior['close']) if prior and prior['close'] else live_price
                change = live_price - prior_close

                prices[symbol] = {
                    'price': round(live_price, 2),
                    'change_24h': round(change, 2)
                }
            else:
                cursor.execute("""
                    SELECT * FROM price_history
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (symbol,))
                latest = cursor.fetchone()
                if latest:
                    prices[symbol] = {
                        'price': round(float(latest['close']), 2),
                        'change_24h': round(float(latest['high']) - float(latest['low']), 2)
                    }

        conn.close()
        return jsonify(prices)

    except Exception as e:
        print(f"Error in get_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({})

@app.route('/api/signals')
def get_signals():
    """NEW: expose the bot's most recent signal per symbol (BUY/SELL/HOLD
    and strength %), so the dashboard can show what the strategy is
    currently thinking, not just past trades."""
    if paper_bot is None:
        return jsonify({})
    return jsonify(paper_bot.last_signals)

@app.route('/api/portfolio/history')
def get_portfolio_history():
    """NEW: last 30 portfolio value snapshots, oldest first, for the hero
    sparkline chart."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, total_portfolio_value
            FROM performance_metrics
            ORDER BY timestamp DESC
            LIMIT 30
        """)
        rows = cursor.fetchall()
        conn.close()

        # Reverse so it's oldest -> newest (left to right on the chart).
        result = [
            {'t': row['timestamp'], 'value': round(float(row['total_portfolio_value']), 2)}
            for row in reversed(rows)
        ]
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_portfolio_history: {e}")
        return jsonify([])

@app.route('/api/price_history')
def get_price_history():
    """NEW: last 20 closes per symbol, oldest first, for the mini sparkline
    on each price card."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        result = {}

        for symbol in ['BTC-USD', 'ETH-USD', 'SOL-USD']:
            cursor.execute("""
                SELECT timestamp, close FROM price_history
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 20
            """, (symbol,))
            rows = cursor.fetchall()
            result[symbol] = [
                {'t': row['timestamp'], 'close': round(float(row['close']), 2)}
                for row in reversed(rows)
            ]

        conn.close()
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_price_history: {e}")
        return jsonify({})

@app.route('/api/bot/status')
def bot_status():
    """Get bot running status, plus a countdown to the next trading cycle."""
    running = paper_bot.is_running if paper_bot else False
    next_check_in = None

    if running and paper_bot.last_cycle_time:
        elapsed = (datetime.now() - paper_bot.last_cycle_time).total_seconds()
        remaining = paper_bot.check_interval - elapsed
        next_check_in = max(0, round(remaining))

    return jsonify({
        'running': running,
        'mode': 'Paper Trading',
        'check_interval_seconds': DASHBOARD_CHECK_INTERVAL,
        'next_check_in': next_check_in
    })

@app.route('/api/stats')
def get_stats():
    """NEW: win rate (from closed BUY->SELL trade pairs) and a session-based
    Sharpe/return computed from this run's own performance_metrics history.

    IMPORTANT: this is deliberately labeled 'session' and kept separate from
    the +40.38% / Sharpe 0.64 backtest figures on the resume/README — those
    came from the original historical backtest, not from live paper trading,
    and conflating the two would be misleading."""
    try:
        import statistics
        from collections import defaultdict

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM trades ORDER BY timestamp ASC")
        trades = cursor.fetchall()

        by_symbol = defaultdict(list)
        for t in trades:
            by_symbol[t['symbol']].append(t)

        wins, losses = 0, 0
        for symbol, tlist in by_symbol.items():
            i = 0
            while i < len(tlist) - 1:
                if (tlist[i]['trade_type'] or '').upper() == 'BUY' and \
                   (tlist[i + 1]['trade_type'] or '').upper() == 'SELL':
                    pnl = (float(tlist[i + 1]['price']) - float(tlist[i]['price'])) * float(tlist[i + 1]['quantity'])
                    wins += 1 if pnl > 0 else 0
                    losses += 1 if pnl <= 0 else 0
                    i += 2
                else:
                    i += 1

        closed_trades = wins + losses
        win_rate = round((wins / closed_trades) * 100, 1) if closed_trades > 0 else None

        cursor.execute("SELECT total_portfolio_value FROM performance_metrics ORDER BY timestamp ASC")
        rows = cursor.fetchall()
        values = [float(r['total_portfolio_value']) for r in rows]

        sharpe_session = None
        total_return_pct = None
        if len(values) >= 2:
            returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values)) if values[i-1]]
            if len(returns) >= 2:
                mean_r = statistics.mean(returns)
                stdev_r = statistics.pstdev(returns)
                sharpe_session = round(mean_r / stdev_r, 2) if stdev_r > 0 else None
            if values[0]:
                total_return_pct = round((values[-1] - values[0]) / values[0] * 100, 2)

        conn.close()
        return jsonify({
            'win_rate': win_rate,
            'closed_trades': closed_trades,
            'wins': wins,
            'losses': losses,
            'sharpe_session': sharpe_session,
            'total_return_pct': total_return_pct
        })
    except Exception as e:
        print(f"Error in get_stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({})

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Actually start the paper trading bot in a background thread."""
    global paper_bot, bot_thread

    if paper_bot is not None and paper_bot.is_running:
        return jsonify({'status': 'already_running', 'message': 'Bot is already running.'})

    paper_bot = PaperTradingBot(symbols=['BTC-USD'])
    paper_bot.check_interval = DASHBOARD_CHECK_INTERVAL

    bot_thread = threading.Thread(target=paper_bot.start, daemon=True)
    bot_thread.start()

    return jsonify({
        'status': 'started',
        'message': f'✅ Bot started — checking every {DASHBOARD_CHECK_INTERVAL // 60} min.'
    })

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Actually stop the paper trading bot (interrupts its wait immediately)."""
    global paper_bot

    if paper_bot is None or not paper_bot.is_running:
        return jsonify({'status': 'not_running', 'message': 'Bot is not currently running.'})

    paper_bot.stop()
    return jsonify({
        'status': 'stopped',
        'message': '⏸️ Bot stopped successfully!'
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Crypto Trading Bot - Web Dashboard")
    print("=" * 60)
    print("📊 Dashboard URL: http://localhost:5001")
    print("🔄 Auto-refresh: Every 5 seconds")
    print("💡 Press Ctrl+C to stop")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5001)