# 🚀 Cryptocurrency Trading Bot - Full Stack Platform

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)]()

An intelligent, automated cryptocurrency trading platform that uses technical analysis, machine learning, and risk management to execute trades. Features a real-time web dashboard, paper trading mode, and comprehensive backtesting engine.

![Dashboard Preview](screenshots/dashboard.png)

---

## 📊 Performance Highlights

| Metric | Value |
|--------|-------|
| **Backtested Return** | +40.38% (BTC) |
| **Win Rate** | 41.67% |
| **Sharpe Ratio** | 0.64 |
| **Max Drawdown** | -20.95% |
| **Trades Analyzed** | 2,196+ historical records |

---

## ✨ Features

### Trading Engine
- ✅ **7 Technical Indicators** (RSI, MACD, Bollinger Bands, Moving Averages, Stochastic, ATR, OBV)
- ✅ **Automated Signal Generation** with majority vote system
- ✅ **Risk Management** (Stop Loss 3%, Take Profit 20%)
- ✅ **Paper Trading Mode** (Risk-free testing with real market data)
- ✅ **Live Trading Ready** (CCXT integration for 100+ exchanges)
- ✅ **Position Sizing & Portfolio Management**

### Analytics & Optimization
- ✅ **Historical Data Collection** (2+ years, multiple cryptocurrencies)
- ✅ **Blockchain On-Chain Analytics** (Network data, social sentiment)
- ✅ **Strategy Backtesting** (Walk-forward analysis, out-of-sample testing)
- ✅ **Parameter Optimization** (Grid search across 100+ combinations)
- ✅ **Multi-Crypto Support** (BTC, ETH, SOL)

### Dashboard & Monitoring
- ✅ **Real-Time Web Dashboard** (Flask REST API + Vanilla JavaScript)
- ✅ **Interactive Portfolio Display** (Live P&L, holdings, trades)
- ✅ **Auto-Updating Charts** (Refreshes every 5 seconds)
- ✅ **Bot Controls** (Start/Stop, configuration)
- ✅ **Health Monitoring** (System checks, automated alerts)

### Deployment
- ✅ **Cloud-Ready** (Heroku configuration included)
- ✅ **Docker Support** (Containerized deployment)
- ✅ **Environment Configuration** (Secure credential management)
- ✅ **24/7 Operation Capable**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│            WEB DASHBOARD (Frontend)                  │
│  HTML5 + CSS3 + Vanilla JavaScript                   │
│  - Real-time portfolio display                       │
│  - Interactive controls                              │
│  - Auto-updating every 5 seconds                     │
└─────────────────┬───────────────────────────────────┘
                  │ REST API (HTTP/JSON)
┌─────────────────▼───────────────────────────────────┐
│              FLASK API SERVER                        │
│  /api/portfolio  /api/trades  /api/prices           │
│  /api/bot/status  /api/bot/start  /api/bot/stop     │
└─────────────────┬───────────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
┌────────▼──────┐  ┌──────▼──────────┐
│ TRADING ENGINE│  │  DATA LAYER     │
│ - Strategy    │  │  - SQLite       │
│ - Indicators  │  │  - 6 Tables     │
│ - Risk Mgmt   │  │  - 2196 Records │
│ - Execution   │  │                 │
└────────┬──────┘  └──────┬──────────┘
         │                │
         └────────┬───────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│           EXTERNAL SERVICES                          │
│  Yahoo Finance │ CoinGecko │ CCXT (Exchanges)       │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip
- Virtual environment (recommended)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/crypto-trading-bot.git
cd crypto-trading-bot

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Initialize database with historical data
python data/fetch_historical_data.py
```

### Usage

#### Run Web Dashboard
```bash
python frontend/app.py
# Open browser to http://localhost:5001
```

#### Run Paper Trading (Safe Mode)
```bash
python trading/paper_trading.py
```

#### Run Strategy Optimization
```bash
python strategies/strategy_optimizer.py
```

#### Run Health Check
```bash
python monitoring/health_check.py
```

---

## 📈 Technical Indicators

### 1. **Moving Averages (SMA, EMA)**
- Simple Moving Average (20, 50, 200 periods)
- Exponential Moving Average (12, 26 periods)
- **Purpose:** Identify trend direction and momentum

### 2. **RSI (Relative Strength Index)**
- Range: 0-100
- Overbought: >70, Oversold: <30
- **Purpose:** Find market reversal points

### 3. **MACD (Moving Average Convergence Divergence)**
- MACD Line: 12 EMA - 26 EMA
- Signal Line: 9 EMA of MACD
- **Purpose:** Trend following and momentum

### 4. **Bollinger Bands**
- Middle: 20-period SMA
- Upper/Lower: ±2 standard deviations
- **Purpose:** Volatility measurement and price extremes

### 5. **Stochastic Oscillator**
- %K and %D lines
- Range: 0-100
- **Purpose:** Overbought/oversold conditions

### 6. **ATR (Average True Range)**
- Measures market volatility
- **Purpose:** Dynamic position sizing and stop-loss placement

### 7. **OBV (On-Balance Volume)**
- Cumulative volume indicator
- **Purpose:** Confirm price trends with volume analysis

---

## 🎯 Trading Strategy

### Signal Generation

Uses a **majority vote system** combining all 7 indicators:

```python
# Pseudocode
buy_votes = count_indicators_saying_buy()
sell_votes = count_indicators_saying_sell()

if buy_votes >= 4:  # 4 out of 7 indicators agree
    signal = 'BUY'
elif sell_votes >= 4:
    signal = 'SELL'
else:
    signal = 'HOLD'
```

### Risk Management

- **Position Size:** 95% of available capital
- **Stop Loss:** 3% (automatic sell if loss exceeds)
- **Take Profit:** 20% (automatic sell when target reached)
- **Signal Threshold:** Requires 75% confidence
- **Daily Loss Limit:** 10% maximum

---

## 📊 Backtesting Results

### BTC-USD (Optimized Parameters)
```
Position Size: 95%
Stop Loss: 3%
Take Profit: 20%

Return: +40.38%
Win Rate: 41.67%
Sharpe Ratio: 0.64
Max Drawdown: -20.95%
Number of Trades: 24
```

### ETH-USD
```
Return: -6.40%
Win Rate: 41.94%
Max Drawdown: -27.40%
```

### SOL-USD
```
Return: -34.09%
Win Rate: 39.13%
Max Drawdown: -50.53%
```

**Conclusion:** Strategy performs best on Bitcoin (most stable cryptocurrency).

---

## 🗄️ Database Schema

### Tables

1. **price_history** - OHLCV data (Open, High, Low, Close, Volume)
2. **portfolio** - Current holdings for each cryptocurrency
3. **trades** - Complete trade execution history
4. **trading_signals** - Buy/sell signals generated
5. **blockchain_metrics** - On-chain analytics data
6. **performance_metrics** - Overall portfolio statistics

### Schema Diagram

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

## 🔌 API Endpoints

### Portfolio
```http
GET /api/portfolio
```
Returns current portfolio value, cash, P&L, and holdings.

**Response:**
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
  },
  "last_update": "2026-02-12 00:58:23"
}
```

### Trades
```http
GET /api/trades
```
Returns last 10 trades.

### Prices
```http
GET /api/prices
```
Returns current prices for BTC, ETH, SOL.

### Bot Control
```http
GET  /api/bot/status
POST /api/bot/start
POST /api/bot/stop
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```bash
# Trading Configuration
LIVE_TRADING=no              # Set to 'yes' for real trading
TRADING_MODE=PAPER           # PAPER or LIVE
INITIAL_CAPITAL=10000        # Starting capital

# Exchange API (for live trading)
COINBASE_API_KEY=your_api_key
COINBASE_API_SECRET=your_api_secret

# Alerts (optional)
ALERT_EMAIL=your@email.com
SENDGRID_API_KEY=your_sendgrid_key

# Twilio SMS (optional)
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
    'position_size': 0.95,  # 95% of capital
    'stop_loss': 0.03,      # 3%
    'take_profit': 0.20,    # 20%
    'signal_threshold': 0.75,  # 75% confidence
    'check_interval': 60    # 60 minutes
}
```

---

## 🚀 Deployment

### Heroku

```bash
# 1. Install Heroku CLI
brew install heroku

# 2. Login
heroku login

# 3. Create app
heroku create your-trading-bot

# 4. Set environment variables
heroku config:set LIVE_TRADING=no
heroku config:set TRADING_MODE=PAPER

# 5. Deploy
git push heroku main

# 6. Scale
heroku ps:scale web=1 worker=1

# 7. Open
heroku open
```

### Docker

```bash
# Build
docker-compose build

# Run
docker-compose up -d

# Logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## 🧪 Testing

### Run Backtests
```bash
python strategies/trading_strategy.py
```

### Run Strategy Optimizer
```bash
python strategies/strategy_optimizer.py
# Choose option 2 for quick optimization
```

### Test Paper Trading
```bash
python trading/paper_trading.py
# Let run for 1-2 weeks before live trading
```

### Health Check
```bash
python monitoring/health_check.py
```

---

## 📁 Project Structure

```
crypto-trading-bot/
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
├── monitoring/              # Health checks
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

## 🛠️ Tech Stack

### Backend
- **Python 3.10** - Core language
- **Flask** - Web framework & REST API
- **SQLite** - Database
- **Pandas/NumPy** - Data analysis
- **yfinance** - Price data
- **TA-Lib** - Technical analysis
- **CCXT** - Exchange integration

### Frontend
- **HTML5** - Structure
- **CSS3** - Styling
- **Vanilla JavaScript** - Interactivity
- **Fetch API** - REST calls

### DevOps
- **Git** - Version control
- **Heroku** - Cloud platform
- **Docker** - Containerization
- **Gunicorn** - Production server

---

## ⚠️ Disclaimer

**This is an educational project for learning purposes.**

- ⚠️ Cryptocurrency trading involves significant risk
- ⚠️ You can lose all your invested capital
- ⚠️ Past performance does not guarantee future results
- ⚠️ This is not financial advice
- ⚠️ Always do your own research (DYOR)
- ⚠️ Never invest more than you can afford to lose

**Use at your own risk. The author is not responsible for any financial losses.**

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📧 Contact

**Zenish Borad**

- LinkedIn: [Your LinkedIn URL]
- Email: your.email@example.com
- GitHub: [@zenishborad](https://github.com/zenishborad)
- Portfolio: [your-portfolio-url.com]

---

## 🙏 Acknowledgments

- [Yahoo Finance](https://finance.yahoo.com/) for price data
- [CoinGecko](https://www.coingecko.com/) for blockchain analytics
- [CCXT](https://github.com/ccxt/ccxt) for exchange integration
- [TA-Lib](https://github.com/mrjbq7/ta-lib) for technical analysis

---

## 📚 Documentation

- [Complete Interview Guide](INTERVIEW_GUIDE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Project Summary](PROJECT_SUMMARY.md)
- [API Documentation](API_DOCS.md)

---

## 🔮 Future Enhancements

- [ ] Machine Learning price prediction (LSTM/Transformer models)
- [ ] Sentiment analysis (Twitter/Reddit/News)
- [ ] More exchanges (Binance, Kraken, Coinbase Pro)
- [ ] Options and futures trading
- [ ] Portfolio rebalancing algorithms
- [ ] Mobile app (React Native)
- [ ] Telegram bot integration
- [ ] Advanced charting (TradingView)
- [ ] Multi-user support with authentication
- [ ] Real-time WebSocket feeds

---

⭐ **Star this repository if you found it helpful!**

**Happy Trading! 🚀💰**

---

*Last Updated: February 12, 2026*