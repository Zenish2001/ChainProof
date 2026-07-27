import yfinance as yf
from data.database import TradingDatabase
import pandas as pd

print("🔍 Checking BTC data in database...")

db = TradingDatabase()

# Get existing BTC data
existing_btc = db.get_price_data('BTC-USD')

if not existing_btc.empty:
    print(f"\n📊 Current BTC records: {len(existing_btc)}")
    print(f"   Date range: {existing_btc.index[0]} to {existing_btc.index[-1]}")
    
    # Find the earliest date we have
    earliest_date = existing_btc.index[0]
    
    print(f"\n🔄 Fetching BTC data before {earliest_date}...")
    
    # Fetch 2 years of data
    ticker = yf.Ticker('BTC-USD')
    df = ticker.history(period='2y', interval='1d')
    
    if not df.empty:
        print(f"   Downloaded {len(df)} records from Yahoo Finance")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        
        # Filter out dates that already exist
        new_data = df[~df.index.isin(existing_btc.index)]
        
        if not new_data.empty:
            print(f"\n✅ Found {len(new_data)} new records to add")
            db.insert_price_data('BTC-USD', new_data)
            print(f"✅ Successfully added new BTC records!")
        else:
            print("\n✅ All BTC data is already up to date!")
    else:
        print("❌ Failed to fetch data from Yahoo Finance")
else:
    print("\n📥 No existing BTC data. Fetching full 2 years...")
    ticker = yf.Ticker('BTC-USD')
    df = ticker.history(period='2y', interval='1d')
    
    if not df.empty:
        db.insert_price_data('BTC-USD', df)
        print(f"✅ Added {len(df)} BTC records")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")

# Show final summary
print("\n" + "="*70)
print("FINAL BTC DATA SUMMARY")
print("="*70)
final_btc = db.get_price_data('BTC-USD')
print(f"Total BTC records: {len(final_btc)}")
print(f"Date range: {final_btc.index[0]} to {final_btc.index[-1]}")
print(f"Latest price: ${final_btc['close'].iloc[-1]:.2f}")
print(f"Highest: ${final_btc['high'].max():.2f}")
print(f"Lowest: ${final_btc['low'].min():.2f}")