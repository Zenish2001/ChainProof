import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('data/trading_bot.db')
c = conn.cursor()

# Clear any existing demo data so this is repeatable
c.execute("DELETE FROM trades")
c.execute("DELETE FROM portfolio")

FEE_RATE = 0.001  # 0.1% per trade

# Completed round-trip trades: (days_ago_buy, buy_price, days_ago_sell, sell_price, qty)
# A realistic mix — wins and one loss — that nets positive
roundtrips = [
    (120, 42000, 110, 48500, 0.22),   # win
    (95,  46000, 80,  44100, 0.20),   # loss (stop-loss style)
    (70,  45500, 55,  53000, 0.21),   # win
    (40,  58000, 28,  61500, 0.16),   # win
]

for buy_days, buy_px, sell_days, sell_px, qty in roundtrips:
    buy_ts  = (datetime.now() - timedelta(days=buy_days)).strftime('%Y-%m-%d %H:%M:%S')
    sell_ts = (datetime.now() - timedelta(days=sell_days)).strftime('%Y-%m-%d %H:%M:%S')
    buy_val, sell_val = buy_px*qty, sell_px*qty

    c.execute("""INSERT INTO trades (symbol,timestamp,trade_type,quantity,price,total_value,fees,status,strategy,notes)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              ('BTC-USD', buy_ts, 'BUY', qty, buy_px, buy_val, buy_val*FEE_RATE,
               'CLOSED', '4/7 Majority Vote', 'Signal: 5/7 indicators bullish'))
    c.execute("""INSERT INTO trades (symbol,timestamp,trade_type,quantity,price,total_value,fees,status,strategy,notes)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              ('BTC-USD', sell_ts, 'SELL', qty, sell_px, sell_val, sell_val*FEE_RATE,
               'CLOSED', '4/7 Majority Vote',
               'Take-profit' if sell_px>buy_px else 'Stop-loss'))

# Current open holding — showing positive unrealized P&L
open_qty, open_entry, current_px = 0.15, 60200, 64319
open_ts = (datetime.now() - timedelta(days=12)).strftime('%Y-%m-%d %H:%M:%S')
open_val = open_entry*open_qty
c.execute("""INSERT INTO trades (symbol,timestamp,trade_type,quantity,price,total_value,fees,status,strategy,notes)
             VALUES (?,?,?,?,?,?,?,?,?,?)""",
          ('BTC-USD', open_ts, 'BUY', open_qty, open_entry, open_val, open_val*FEE_RATE,
           'OPEN', '4/7 Majority Vote', 'Signal: 4/7 indicators bullish'))

# Portfolio row for the open holding
cur_val = current_px*open_qty
pl = cur_val - open_val
pl_pct = (pl/open_val)*100
c.execute("""INSERT INTO portfolio (symbol,quantity,avg_buy_price,current_price,total_value,profit_loss,profit_loss_percent,last_updated)
             VALUES (?,?,?,?,?,?,?,?)""",
          ('BTC-USD', open_qty, open_entry, current_px, cur_val, pl, pl_pct,
           datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

conn.commit()

# Summary
trades = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
print(f"Inserted {trades} trades and 1 open holding.")
print(f"Open BTC position: {open_qty} BTC, entry ${open_entry}, now ${current_px}, P&L ${pl:.2f} ({pl_pct:+.2f}%)")
conn.close()