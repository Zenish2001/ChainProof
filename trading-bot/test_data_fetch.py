import yfinance as yf
from data.database import TradingDatabase

print("Starting data fetch test...")

# Initialize database
db = TradingDatabase()
print("Database connected!")

# Test with just BTC
symbol = 'BTC-USD'
print(f"\nFetching {symbol}...")

ticker = yf.Ticker(symbol)
df = ticker.history(period='1mo', interval='1d')

print(f"Downloaded {len(df)} records")
print(f"Date range: {df.index[0]} to {df.index[-1]}")
print(f"Latest price: ${df['Close'].iloc[-1]:.2f}")

# Store in database
db.insert_price_data(symbol, df)

print("\n✅ Test complete!")