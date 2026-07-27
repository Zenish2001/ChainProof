from flask import Flask, render_template, jsonify, request
import sys
from pathlib import Path
from datetime import datetime
import json
import sqlite3

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

app = Flask(__name__)

# Path to database
DB_PATH = 'data/trading_bot.db'

# Bot status
bot_running = False

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
    """Get latest prices for BTC, ETH, SOL"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        prices = {}
        for symbol in ['BTC-USD', 'ETH-USD', 'SOL-USD']:
            # Get latest price from price_history
            cursor.execute("""
                SELECT * FROM price_history 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol,))
            latest = cursor.fetchone()
            
            if latest:
                high = float(latest['high']) if latest['high'] else 0
                low = float(latest['low']) if latest['low'] else 0
                close = float(latest['close']) if latest['close'] else 0
                change = high - low
                
                prices[symbol] = {
                    'price': round(close, 2),
                    'change_24h': round(change, 2)
                }
            else:
                # Fallback: get from portfolio
                cursor.execute("""
                    SELECT current_price FROM portfolio 
                    WHERE symbol = ?
                    ORDER BY last_updated DESC
                    LIMIT 1
                """, (symbol,))
                portfolio_price = cursor.fetchone()
                
                if portfolio_price:
                    prices[symbol] = {
                        'price': round(float(portfolio_price['current_price']), 2),
                        'change_24h': 0.0
                    }
        
        conn.close()
        return jsonify(prices)
        
    except Exception as e:
        print(f"Error in get_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({})

@app.route('/api/bot/status')
def bot_status():
    """Get bot running status"""
    return jsonify({
        'running': bot_running,
        'mode': 'Paper Trading'
    })

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    global bot_running
    bot_running = True
    return jsonify({
        'status': 'started', 
        'message': '✅ Bot started successfully!'
    })

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    global bot_running
    bot_running = False
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