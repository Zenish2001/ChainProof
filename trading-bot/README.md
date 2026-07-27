# Cryptocurrency Trading Bot — Full Stack Platform

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-2ea44f?style=for-the-badge)]()

An automated cryptocurrency trading platform that uses technical analysis and risk management to generate and execute trades. Includes a real-time web dashboard, a paper trading mode, and a full backtesting engine.

---

## Performance Highlights

| Metric | Value |
|---|---|
| Backtested Return (BTC-USD) | +40.38% |
| Win Rate | 41.67% |
| Sharpe Ratio | 0.64 |
| Max Drawdown | -20.95% |
| Historical Records Analyzed | 2,196+ |

---

## Features

**Trading Engine**
- 7 technical indicators (RSI, MACD, Bollinger Bands, Moving Averages, Stochastic, ATR, OBV)
- Automated signal generation via a majority-vote system
- Risk management (3% stop loss, 20% take profit)
- Paper trading mode for risk-free testing with real market data
- Live trading ready via CCXT, supporting 100+ exchanges
- Position sizing and portfolio management

**Analytics & Optimization**
- 2+ years of historical data across multiple cryptocurrencies
- On-chain analytics (network data, sentiment)
- Strategy backtesting with walk-forward and out-of-sample testing
- Parameter optimization via grid search across 100+ combinations
- Multi-crypto support (BTC, ETH, SOL)

**Dashboard & Monitoring**
- Real-time web dashboard (Flask REST API + vanilla JavaScript)
- Interactive portfolio display with live P&L, holdings, and trades
- Auto-updating charts, refreshed every 5 seconds
- Bot controls for start/stop and configuration
- Health monitoring with automated alerts

**Deployment**
- Cloud-ready with included Heroku configuration
- Docker support for containerized deployment
- Secure environment-based credential management
- Designed for 24/7 operation

---

## Architecture

```
                    Web Dashboard (Frontend)
              HTML5 + CSS3 + Vanilla JavaScript
        Real-time portfolio display, interactive controls,
                 auto-updating every 5 seconds
                            |
                    REST API (HTTP/JSON)
                            |
                     Flask API Server
      /api/portfolio  /api/trades  /api/prices
      /api/bot/status  /api/bot/start  /api/bot/stop
                            |
              -----------------------------
              |                           |
      Trading Engine                 Data Layer
      Strategy, indicators,          SQLite, 6 tables,
      risk management, execution     2,196 records
              |                           |
              -----------------------------
                            |
                   External Services
        Yahoo Finance, CoinGecko, CCXT (exchanges)
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip
- Virtual environment (recommended)

### Installation

```bash
git clone https://github.com/Zenish2001/ChainProof.git
cd ChainProof/trading-bot

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your settings

python data/fetch_historical_data.py
```

### Usage

Run the web dashboard:
```bash
python frontend/app.py
# Open browser to http://localhost:5001
```

Run paper trading (safe mode):
```bash
python trading/paper_trading.py
```

Run strategy optimization:
```bash
python strategies/strategy_optimizer.py
```

Run a health check:
```bash
python monitoring/health_check.py
```

---

## Technical Indicators

**Moving Averages (SMA, EMA)** — Simple (20, 50, 200 periods) and Exponential (12, 26 periods). Used to identify trend direction and momentum.

**RSI (Relative Strength Index)** — Range 0-100; overbought above 70, oversold below 30. Used to find market reversal points.

**MACD (Moving Average Convergence Divergence)** — MACD line (12 EMA − 26 EMA), signal line (9 EMA of MACD). Used for trend following and momentum.

**Bollinger Bands** — 20-period SMA with ±2 standard deviation bands. Used to measure volatility and price extremes.

**Stochastic Oscillator** — %K and %D lines, range 0-100. Used to detect overbought/oversold conditions.

**ATR (Average True Range)** — Measures market volatility. Used for dynamic position sizing and stop-loss placement.

**OBV (On-Balance Volume)** — Cumulative volume indicator, used to confirm price trends with volume analysis.

---

## Trading Strategy

### Signal Generation

A majority-vote system combines all 7 indicators:

```python
buy_votes = count_indicators_saying_buy()
sell_votes = count_indicators_saying_sell()

if buy_votes >= 4:
    signal = 'BUY'
elif sell_votes >= 4:
    signal = 'SELL'
else:
    signal = 'HOLD'
```

### Risk Management

- Position size: 95% of available capital
- Stop loss: 3% (automatic sell if loss exceeds threshold)
- Take profit: 20% (automatic sell when target reached)
- Signal threshold: requires 75% confidence
- Daily loss limit: 10% maximum

---

## Backtesting Results

**BTC-USD (optimized parameters)**

| Metric | Value |
|---|---|
| Return | +40.38% |
| Win Rate | 41.67% |
| Sharpe Ratio | 0.64 |
| Max Drawdown | -20.95% |
| Trades | 24 |

**ETH-USD** — Return: -6.40%, Win Rate: 41.94%, Max Drawdown: -27.40%

**SOL-USD** — Return: -34.09%, Win Rate: 39.13%, Max Drawdown: -50.53%

The strategy performs best on Bitcoin, the most stable of the three assets tested.

---

## Database Schema

**Tables**
1. `price_history` — OHLCV data (open, high, low, close, volume)
2. `portfolio` — current holdings per cryptocurrency
3. `trades` — complete trade execution history
4. `trading_signals` — generated buy/sell signals
5. `blockchain_metrics` — on-chain analytics data
6. `performance_metrics` — overall portfolio statistics

```sql
price_history
├── id (PK)
├── symbol
├── timestamp
├── open, high, low, close
└── volume

portfolio
├── id (PK)
├── symbol
├── quantity
├── avg_buy_price
├── current_price
└── last_updated

trades
├── id (PK)
├── symbol
├── timestamp
├── trade_type (BUY/SELL)
├── quantity
├── price
└── total_value
```

---

## API Endpoints

**Portfolio**
```http
GET /api/portfolio
```
Returns current portfolio value, cash, P&L, and holdings.

```json
{
  "total_value": 10456.78,
  "cash": 2345.67,
  "pnl": 456.78,
  "pnl_percent": 4.57,
  "holdings": {
    "BTC-USD": {
      "quantity": 0.156,
      "current_value": 8234.45,
      "cost_basis": 8000.00
    }
  }
}
```

**Trades**
```http
GET /api/trades
```
Returns the last 10 trades.

**Prices**
```http
GET /api/prices
```
Returns current prices for BTC, ETH, and SOL.

**Bot Control**
```http
GET  /api/bot/status
POST /api/bot/start
POST /api/bot/stop
```

---

## Configuration

### Environment Variables

Create a `.env` file:

```bash
LIVE_TRADING=no
TRADING_MODE=PAPER
INITIAL_CAPITAL=10000

COINBASE_API_KEY=your_api_key
COINBASE_API_SECRET=your_api_secret

ALERT_EMAIL=your@email.com
SENDGRID_API_KEY=your_sendgrid_key

TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
ALERT_PHONE=+1234567890
```

### Strategy Parameters

Edit `trading/paper_trading.py`:

```python
CONFIG = {
    'symbols': ['BTC-USD', 'ETH-USD', 'SOL-USD'],
    'initial_capital': 10000,
    'position_size': 0.95,
    'stop_loss': 0.03,
    'take_profit': 0.20,
    'signal_threshold': 0.75,
    'check_interval': 60
}
```

---

## Deployment

### Heroku
```bash
brew install heroku
heroku login
heroku create your-trading-bot
heroku config:set LIVE_TRADING=no
heroku config:set TRADING_MODE=PAPER
git push heroku main
heroku ps:scale web=1 worker=1
heroku open
```

### Docker
```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
docker-compose down
```

---

## Testing

```bash
# Run backtests
python strategies/trading_strategy.py

# Run strategy optimizer
python strategies/strategy_optimizer.py

# Test paper trading
python trading/paper_trading.py

# Health check
python monitoring/health_check.py
```

---

## Project Structure

```
trading-bot/
├── data/                    # Data collection & storage
│   ├── database.py
│   ├── price_fetcher.py
│   ├── fetch_historical_data.py
│   └── trading_bot.db
├── indicators/              # Technical analysis
│   └── technical_indicators.py
├── strategies/              # Trading logic
│   ├── trading_strategy.py
│   ├── backtest.py
│   └── strategy_optimizer.py
├── blockchain/              # On-chain analytics
│   └── blockchain_analytics.py
├── trading/                 # Execution
│   ├── paper_trading.py
│   └── live_trading.py
├── frontend/                # Web dashboard
│   ├── app.py
│   ├── templates/
│   │   └── dashboard.html
│   └── static/
│       ├── css/style.css
│       └── js/script.js
├── monitoring/               # Health checks
│   ├── __init__.py
│   └── health_check.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Tech Stack

**Backend:** Python 3.10, Flask, SQLite, Pandas/NumPy, yfinance, TA-Lib, CCXT
**Frontend:** HTML5, CSS3, Vanilla JavaScript, Fetch API
**DevOps:** Git, Heroku, Docker, Gunicorn

---

## License

MIT License — see [LICENSE](../LICENSE)

---

## Contact

**Zenish Borad**
LinkedIn: [zenish-borad](https://www.linkedin.com/in/zenish-borad)
Email: [zenish42@gmail.com](mailto:zenish42@gmail.com)
GitHub: [@Zenish2001](https://github.com/Zenish2001)
