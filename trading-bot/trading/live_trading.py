import time
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.database import TradingDatabase
from indicators.technical_indicators import TechnicalIndicators
import yfinance as yf

# For Coinbase (you'll need to install: pip install coinbase-advanced-py)
try:
    from coinbase.rest import RESTClient
    COINBASE_AVAILABLE = True
except ImportError:
    COINBASE_AVAILABLE = False
    print("Warning: coinbase-advanced-py not installed. Install with: pip install coinbase-advanced-py")

class LiveTradingBot:
    """
    LIVE TRADING BOT - Executes real trades with real money
    
    WARNINGS:
    - This bot trades with REAL MONEY
    - You can LOSE money
    - Start with small amounts
    - Test thoroughly in paper trading first
    - Never invest more than you can afford to lose
    """
    
    def __init__(self, exchange='coinbase', api_key=None, api_secret=None,
                 symbols=['BTC-USD'], position_size=0.95, 
                 stop_loss=0.03, take_profit=0.20, 
                 max_daily_loss=0.10, dry_run=True):
        """
        Initialize live trading bot
        
        Parameters:
        - exchange: 'coinbase' or other (currently only Coinbase supported)
        - api_key: Your exchange API key
        - api_secret: Your exchange API secret
        - symbols: List of trading pairs
        - position_size: Percentage of portfolio to use per trade
        - stop_loss: Stop loss percentage
        - take_profit: Take profit percentage
        - max_daily_loss: Maximum daily loss before stopping (safety feature)
        - dry_run: If True, simulate trades without executing (RECOMMENDED for first run)
        """
        
        self.db = TradingDatabase()
        self.exchange = exchange
        self.symbols = symbols
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_daily_loss = max_daily_loss
        self.dry_run = dry_run
        
        # Trading state
        self.is_running = False
        self.daily_pnl = 0
        self.daily_start_value = 0
        self.check_interval = 3600  # 1 hour
        
        # Initialize exchange connection
        if not dry_run:
            if exchange == 'coinbase':
                if not COINBASE_AVAILABLE:
                    raise ImportError("Coinbase library not installed")
                if not api_key or not api_secret:
                    raise ValueError("API key and secret required for live trading")
                self.client = RESTClient(api_key=api_key, api_secret=api_secret)
            else:
                raise ValueError(f"Exchange {exchange} not supported yet")
        else:
            self.client = None
        
        print("\n" + "="*70)
        print("⚠️  LIVE TRADING BOT INITIALIZED ⚠️")
        print("="*70)
        if dry_run:
            print("MODE: DRY RUN (Simulated trades only)")
        else:
            print("MODE: LIVE TRADING (REAL MONEY!)")
        print(f"Exchange: {exchange}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Position Size: {position_size*100:.0f}%")
        print(f"Stop Loss: {stop_loss*100:.0f}%")
        print(f"Take Profit: {take_profit*100:.0f}%")
        print(f"Max Daily Loss: {max_daily_loss*100:.0f}%")
        print("="*70 + "\n")
    
    def get_account_balance(self):
        """Get current account balance"""
        if self.dry_run:
            return {'USD': 10000, 'BTC': 0, 'ETH': 0, 'SOL': 0}
        
        try:
            accounts = self.client.get_accounts()
            balance = {}
            for account in accounts['accounts']:
                currency = account['currency']
                available = float(account['available_balance']['value'])
                balance[currency] = available
            return balance
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return None
    
    def get_current_price(self, symbol):
        """Get current market price"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1m')
            if not data.empty:
                return data['Close'].iloc[-1]
            return None
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
            return None
    
    def get_positions(self):
        """Get current open positions"""
        if self.dry_run:
            # In dry run, track positions in database
            portfolio = self.db.get_portfolio()
            return portfolio
        
        try:
            balance = self.get_account_balance()
            positions = {}
            for symbol in self.symbols:
                crypto = symbol.split('-')[0]
                if crypto in balance and balance[crypto] > 0:
                    positions[symbol] = {
                        'quantity': balance[crypto],
                        'current_value': balance[crypto] * self.get_current_price(symbol)
                    }
            return positions
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return {}
    
    def place_market_buy(self, symbol, usd_amount):
        """Place a market buy order"""
        print(f"\n{'='*70}")
        print(f"EXECUTING BUY ORDER")
        print(f"{'='*70}")
        print(f"Symbol: {symbol}")
        print(f"Amount: ${usd_amount:,.2f}")
        
        if self.dry_run:
            print("DRY RUN: Order simulated, not executed")
            current_price = self.get_current_price(symbol)
            quantity = usd_amount / current_price
            
            # Record in database
            self.db.insert_trade(
                symbol=symbol,
                trade_type='BUY',
                quantity=quantity,
                price=current_price,
                strategy='live_trading_dry_run'
            )
            
            print(f"Price: ${current_price:,.2f}")
            print(f"Quantity: {quantity:.8f}")
            print(f"{'='*70}\n")
            return True
        
        try:
            # Convert symbol format (BTC-USD to BTC-USD for Coinbase)
            order = self.client.market_order_buy(
                client_order_id=f"buy_{int(time.time())}",
                product_id=symbol,
                quote_size=str(usd_amount)
            )
            
            print(f"Order placed successfully!")
            print(f"Order ID: {order.get('order_id', 'N/A')}")
            
            # Record in database
            fills = order.get('fills', [])
            if fills:
                fill = fills[0]
                self.db.insert_trade(
                    symbol=symbol,
                    trade_type='BUY',
                    quantity=float(fill['size']),
                    price=float(fill['price']),
                    strategy='live_trading'
                )
            
            print(f"{'='*70}\n")
            return True
            
        except Exception as e:
            print(f"Error placing buy order: {e}")
            print(f"{'='*70}\n")
            return False
    
    def place_market_sell(self, symbol, quantity):
        """Place a market sell order"""
        print(f"\n{'='*70}")
        print(f"EXECUTING SELL ORDER")
        print(f"{'='*70}")
        print(f"Symbol: {symbol}")
        print(f"Quantity: {quantity:.8f}")
        
        if self.dry_run:
            print("DRY RUN: Order simulated, not executed")
            current_price = self.get_current_price(symbol)
            sale_value = quantity * current_price
            
            # Record in database
            self.db.insert_trade(
                symbol=symbol,
                trade_type='SELL',
                quantity=quantity,
                price=current_price,
                strategy='live_trading_dry_run'
            )
            
            print(f"Price: ${current_price:,.2f}")
            print(f"Sale Value: ${sale_value:,.2f}")
            print(f"{'='*70}\n")
            return True
        
        try:
            order = self.client.market_order_sell(
                client_order_id=f"sell_{int(time.time())}",
                product_id=symbol,
                base_size=str(quantity)
            )
            
            print(f"Order placed successfully!")
            print(f"Order ID: {order.get('order_id', 'N/A')}")
            
            # Record in database
            fills = order.get('fills', [])
            if fills:
                fill = fills[0]
                self.db.insert_trade(
                    symbol=symbol,
                    trade_type='SELL',
                    quantity=float(fill['size']),
                    price=float(fill['price']),
                    strategy='live_trading'
                )
            
            print(f"{'='*70}\n")
            return True
            
        except Exception as e:
            print(f"Error placing sell order: {e}")
            print(f"{'='*70}\n")
            return False
    
    def check_daily_loss_limit(self):
        """Check if daily loss limit has been reached"""
        if abs(self.daily_pnl) >= (self.daily_start_value * self.max_daily_loss):
            print("\n" + "="*70)
            print("⚠️  DAILY LOSS LIMIT REACHED - STOPPING TRADING ⚠️")
            print("="*70)
            print(f"Daily P/L: ${self.daily_pnl:,.2f}")
            print(f"Max Daily Loss: ${self.daily_start_value * self.max_daily_loss:,.2f}")
            print("="*70 + "\n")
            return True
        return False
    
    def generate_signal(self, symbol):
        """Generate trading signal"""
        df = self.db.get_price_data(symbol)
        
        if df.empty or len(df) < 50:
            return 'HOLD', 0
        
        signals, _ = TechnicalIndicators.generate_signals(df)
        latest = signals.iloc[-1]
        
        return latest['overall_signal'], latest['signal_strength']
    
    def run_trading_cycle(self):
        """Run one trading cycle"""
        print(f"\n{'='*70}")
        print(f"TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # Check daily loss limit
        if self.check_daily_loss_limit():
            self.stop()
            return
        
        # Get current balance
        balance = self.get_account_balance()
        if balance:
            print(f"Account Balance:")
            for currency, amount in balance.items():
                if amount > 0:
                    print(f"  {currency}: {amount:,.2f}")
            print()
        
        # Analyze each symbol
        for symbol in self.symbols:
            print(f"Analyzing {symbol}...")
            
            # Get current price
            current_price = self.get_current_price(symbol)
            if not current_price:
                continue
            
            print(f"Current Price: ${current_price:,.2f}")
            
            # Generate signal
            signal, strength = self.generate_signal(symbol)
            print(f"Signal: {signal} (Strength: {strength:.0f}%)")
            
            # Get positions
            positions = self.get_positions()
            
            # Trading logic
            if signal == 'BUY' and strength >= 75:
                # Check if we already have a position
                if symbol not in positions or positions.empty:
                    usd_balance = balance.get('USD', 0) if balance else 10000
                    investment = usd_balance * self.position_size
                    
                    if investment >= 10:  # Minimum $10 order
                        print(f"BUY signal triggered with {strength:.0f}% strength")
                        self.place_market_buy(symbol, investment)
                    else:
                        print(f"Insufficient balance for trade (need $10 minimum)")
                else:
                    print(f"Already holding position in {symbol}")
            
            elif signal == 'SELL' and strength >= 75:
                # Check if we have a position to sell
                if not positions.empty and symbol in positions['symbol'].values:
                    position = positions[positions['symbol'] == symbol].iloc[0]
                    quantity = position['quantity']
                    
                    print(f"SELL signal triggered with {strength:.0f}% strength")
                    self.place_market_sell(symbol, quantity)
                else:
                    print(f"No position to sell in {symbol}")
            else:
                print(f"No action (signal not strong enough or already positioned)")
            
            print()
        
        print(f"{'='*70}\n")
    
    def start(self):
        """Start the live trading bot"""
        self.is_running = True
        
        # Get starting portfolio value
        balance = self.get_account_balance()
        if balance:
            self.daily_start_value = balance.get('USD', 10000)
        
        print("\n" + "="*70)
        if self.dry_run:
            print("🔧 LIVE TRADING BOT STARTED (DRY RUN MODE)")
        else:
            print("⚠️  LIVE TRADING BOT STARTED (REAL MONEY!) ⚠️")
        print("="*70)
        print("Press Ctrl+C to stop")
        print("="*70 + "\n")
        
        try:
            while self.is_running:
                self.run_trading_cycle()
                
                print(f"Waiting {self.check_interval//60} minutes until next check...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\nStopping bot...")
            self.stop()
    
    def stop(self):
        """Stop the bot"""
        self.is_running = False
        print("\n" + "="*70)
        print("LIVE TRADING BOT STOPPED")
        print("="*70 + "\n")


# Run live trading bot
if __name__ == "__main__":
    print("\n" + "="*70)
    print("⚠️  LIVE TRADING BOT SETUP ⚠️")
    print("="*70)
    print("\nWARNING: This bot trades with REAL MONEY!")
    print("Only proceed if you understand the risks.\n")
    
    # Dry run mode (HIGHLY RECOMMENDED for first time)
    mode = input("Run in DRY RUN mode? (y/n, default: y): ").strip().lower()
    dry_run = mode != 'n'
    
    if not dry_run:
        print("\n⚠️  YOU ARE ABOUT TO ENABLE LIVE TRADING WITH REAL MONEY ⚠️")
        confirm = input("Type 'I UNDERSTAND THE RISKS' to continue: ").strip()
        if confirm != "I UNDERSTAND THE RISKS":
            print("Setup cancelled.")
            exit()
        
        # Get API credentials
        print("\nEnter your Coinbase API credentials:")
        api_key = input("API Key: ").strip()
        api_secret = input("API Secret: ").strip()
    else:
        api_key = None
        api_secret = None
        print("\nRunning in DRY RUN mode - trades will be simulated\n")
    
    # Configuration
    symbols_input = input("Symbols (comma-separated, default: BTC-USD): ").strip()
    symbols = [s.strip() for s in symbols_input.split(',')] if symbols_input else ['BTC-USD']
    
    # Create bot
    bot = LiveTradingBot(
        exchange='coinbase',
        api_key=api_key,
        api_secret=api_secret,
        symbols=symbols,
        position_size=0.95,
        stop_loss=0.03,
        take_profit=0.20,
        max_daily_loss=0.10,
        dry_run=dry_run
    )
    
    # Start trading
    bot.start()