<div align="center">

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=120&section=header&text=Trading%20Bot&fontSize=42&fontColor=ffffff&fontAlignY=55" width="100%"/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](../LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-2ea44f?style=for-the-badge)]()

</div>

An automated cryptocurrency trading platform that uses technical analysis and risk management to generate and execute trades. Includes a real-time web dashboard, a paper trading mode, and a full backtesting engine. This module is the foundation that [ChainProof's verification layer](../verification-layer/) builds on.

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Contents

- [Performance Highlights](#performance-highlights)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Technical Indicators](#technical-indicators)
- [Trading Strategy](#trading-strategy)
- [Backtesting Results](#backtesting-results)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Screenshots

<div align="center">

**Live dashboard — real-time prices, current signal, session performance**

<img src="screenshots/trading-bot-overview.png" width="90%"/>

<br/><br/>

**Holdings and trade history**

<img src="screenshots/trading-bot-holdings.png" width="90%"/>

</div>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Performance Highlights

<div align="center">

| Metric | Value |
|:---|:---:|
| Backtested Return (BTC-USD, best of grid search) | **+38.47%** |
| Win Rate | **41.67%** |
| Sharpe Ratio | **0.64** |
| Max Drawdown | **-20.95%** |
| Historical Records Analyzed | **2,196+** |

</div>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Features

<table>
<tr>
<td valign="top" width="25%">

**Trading Engine**
- 7 technical indicators computed, 4 voting
- 2-of-4 signal generation
- Risk management (3% stop loss, 20% take profit)
- Paper trading mode
- Live trading via CCXT (100+ exchanges)
- Position sizing & portfolio management

</td>
<td valign="top" width="25%">

**Analytics & Optimization**
- 2+ years of historical data, multiple assets
- On-chain analytics (network data, sentiment)
- Grid search parameter optimization
- Multi-crypto support (BTC, ETH, SOL)

</td>
<td valign="top" width="25%">

**Dashboard & Monitoring**
- Real-time dashboard (Flask + vanilla JS)
- Live P&L, holdings, and trade history
- Auto-updating charts (5s refresh)
- Bot start/stop controls
- Automated health checks & alerts

</td>
<td valign="top" width="25%">

**Deployment**
- Heroku-ready configuration
- Docker support
- Secure environment-based credentials
- Built for 24/7 operation

</td>
</tr>
</table>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Technical Indicators

<div align="center">

| Indicator | Configuration | Role |
|---|---|---|
| RSI | Buy < 30, sell > 70 | **Votes** |
| MACD | 12 EMA − 26 EMA vs 9 EMA signal line | **Votes** |
| Moving-average crossover | SMA 20 vs SMA 50 | **Votes** |
| Bollinger Bands | 20-period SMA, ±2 std dev; buy below lower, sell above upper | **Votes** |
| Stochastic Oscillator | %K / %D, range 0-100 | Computed and displayed, not voting |
| ATR | Average True Range | Computed and displayed, not voting |
| OBV | Cumulative volume | Computed and displayed, not voting |

</div>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Trading Strategy

### Signal Generation

Four indicators vote BUY, SELL or HOLD. The overall signal comes from
`TechnicalIndicators.generate_signals()`:

```python
buy_count  = number of voting indicators saying BUY    # out of 4
sell_count = number of voting indicators saying SELL   # out of 4

if buy_count >= 2:  signal = 'BUY'
if sell_count >= 2: signal = 'SELL'   # applied second, so a 2-2 tie resolves to SELL
otherwise:          signal = 'HOLD'

signal_strength = agreeing_votes / 4 * 100   # 50, 75 or 100
```

The backtester (`execute_backtest`) enters on any BUY signal, i.e. 2 of 4 votes.
Paper and live trading are stricter and require `signal_strength >= 75`
(3 of 4 votes).

### Risk Management

- Position size: 95% of available capital
- Stop loss: 3% (automatic sell if loss exceeds threshold)
- Take profit: 20% (automatic sell when target reached)
- Signal threshold: paper/live trading requires 75% strength (3 of 4 votes); the backtester trades at 50% (2 of 4)
- Daily loss limit: 10% maximum

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Backtesting Results

<div align="center">

**BTC-USD (optimized parameters)**

| Metric | Value |
|:---|:---:|
| Return | **+38.47%** |
| Win Rate | 41.67% |
| Sharpe Ratio | 0.64 |
| Max Drawdown | -20.95% |
| Trades | 24 |

| Asset | Return | Win Rate | Max Drawdown |
|:---|:---:|:---:|:---:|
| ETH-USD | -6.40% | 41.94% | -27.40% |
| SOL-USD | -34.09% | 39.13% | -50.53% |

</div>

The strategy performs best on Bitcoin, the most stable of the three assets tested.

**How to read these numbers.** Each row is the best configuration from a grid
search over position size, stop-loss and take-profit, scored on the same
historical data it was selected on, so the results are in-sample. The
backtester also fills at the signal bar's close and does not model trading
fees or slippage. Treat the figures as a description of this strategy on
this history, not a forecast. The full sweep output is in
[`results/strategy_comparison.csv`](../verification-layer/results/strategy_comparison.csv).

`evaluate_backtest.py` reports what the headline leaves out: the
buy-and-hold return over the same window, the result after a cost per
side, and an out-of-sample run in which parameters chosen on the first 70%
of the history trade the remaining 30% unchanged.

```bash
python evaluate_backtest.py --db data/trading_bot.db --cost 0.001
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Database Schema

**Tables:** `price_history`, `portfolio`, `trades`, `trading_signals`, `blockchain_metrics`, `performance_metrics`

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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## API Endpoints

| Endpoint | Method | Description |
|---|:---:|---|
| `/api/portfolio` | GET | Portfolio value, cash, P&L, and holdings |
| `/api/trades` | GET | Last 10 trades |
| `/api/prices` | GET | Current prices for BTC, ETH, SOL |
| `/api/bot/status` | GET | Current bot status |
| `/api/bot/start` | POST | Start the bot |
| `/api/bot/stop` | POST | Stop the bot |

**Example response — `GET /api/portfolio`**
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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Deployment

**Heroku**
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

**Docker**
```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
docker-compose down
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Project Structure

```
trading-bot/
├── data/                    # Data collection & storage (not yet in this repository)
│   ├── database.py
│   ├── price_fetcher.py
│   ├── fetch_historical_data.py
│   └── trading_bot.db
├── indicators/              # Technical analysis
│   └── technical_indicators.py
├── strategies/              # Trading logic
│   ├── trading_strategy.py
│   └── strategy_optimizer.py
├── blockchain/              # On-chain analytics (not yet in this repository)
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
├── screenshots/              # Dashboard screenshots
│   ├── trading-bot-overview.png
│   └── trading-bot-holdings.png
├── requirements.txt
├── Procfile
├── runtime.txt
├── .env.example
├── .gitignore
└── README.md
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## Tech Stack

<div align="center">

<img src="https://skillicons.dev/icons?i=python,flask,sqlite,git,html,css,js&theme=dark" />

</div>

<br/>

**Backend:** Python 3.10, Flask, SQLite, Pandas/NumPy, yfinance, TA-Lib, CCXT
**Frontend:** HTML5, CSS3, Vanilla JavaScript, Fetch API
**DevOps:** Git, Heroku, Docker, Gunicorn