import time
import yfinance as yf
from datetime import datetime
import sys
import os
import json
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.database import TradingDatabase
from indicators.technical_indicators import TechnicalIndicators

class PaperTradingBot:
    """
    Paper trading bot that runs in real-time with simulated trades
    """
    
    def __init__(self, symbols=['BTC-USD'], initial_capital=10000, 
                 position_size=0.95, stop_loss=0.03, take_profit=0.20):
        """
        Initialize paper trading bot
        """
        self.db = TradingDatabase()
        self.symbols = symbols
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        # Portfolio state
        self.portfolio = {
            'cash': initial_capital,
            'positions': {},  # {symbol: {'quantity': float, 'entry_price': float, 'entry_date': datetime}}
            'total_value': initial_capital,
            'total_profit_loss': 0
        }
        
        # Trading state
        self.is_running = False
        self.check_interval = 3600  # Check every hour (in seconds)

        # Interruptible wait: lets stop() end the sleep immediately instead
        # of blocking until the full check_interval elapses.
        self._stop_event = threading.Event()

        # Most recent signal per symbol, for the dashboard to display.
        self.last_signals = {}

        # Timestamp of the start of the most recent trading cycle, so the
        # dashboard can compute a countdown to the next check.
        self.last_cycle_time = None
        
        # Load portfolio if exists
        self.load_portfolio()
        
        print("\n" + "="*70)
        print("PAPER TRADING BOT INITIALIZED")
        print("="*70)
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Position Size: {self.position_size*100:.0f}%")
        print(f"Stop Loss: {self.stop_loss*100:.0f}%")
        print(f"Take Profit: {self.take_profit*100:.0f}%")
        print(f"Check Interval: Every {self.check_interval//60} minutes")
        print("="*70 + "\n")
    
    def save_portfolio(self):
        """Save portfolio state to file"""
        with open('data/paper_portfolio.json', 'w') as f:
            # Convert datetime to string for JSON
            portfolio_copy = self.portfolio.copy()
            if 'positions' in portfolio_copy:
                for symbol in portfolio_copy['positions']:
                    if 'entry_date' in portfolio_copy['positions'][symbol]:
                        portfolio_copy['positions'][symbol]['entry_date'] = \
                            portfolio_copy['positions'][symbol]['entry_date'].isoformat()
            json.dump(portfolio_copy, f, indent=2)
    
    def load_portfolio(self):
        """Load portfolio state from file"""
        try:
            with open('data/paper_portfolio.json', 'r') as f:
                saved = json.load(f)
                self.portfolio = saved
                # Convert string back to datetime
                if 'positions' in self.portfolio:
                    for symbol in self.portfolio['positions']:
                        if 'entry_date' in self.portfolio['positions'][symbol]:
                            self.portfolio['positions'][symbol]['entry_date'] = \
                                datetime.fromisoformat(self.portfolio['positions'][symbol]['entry_date'])
                print("Portfolio loaded from previous session")
        except FileNotFoundError:
            print("No previous portfolio found, starting fresh")
    
    def fetch_current_price(self, symbol):
        """Fetch current price for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1m')
            if not data.empty:
                return data['Close'].iloc[-1]
            return None
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
            return None
    
    def get_historical_data(self, symbol, days=30):
        """Get historical data for analysis"""
        df = self.db.get_price_data(symbol)
        if df.empty:
            # Fetch from Yahoo if not in database
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f'{days}d', interval='1d')
            if not df.empty:
                self.db.insert_price_data(symbol, df)
        return df
    
    def generate_signal(self, symbol):
        """Generate trading signal for a symbol"""
        df = self.get_historical_data(symbol)
        
        if df.empty or len(df) < 50:
            return 'HOLD', 0, {}
        
        # Generate signals
        signals, df_with_indicators = TechnicalIndicators.generate_signals(df)
        latest_signal = signals.iloc[-1]
        
        return latest_signal['overall_signal'], latest_signal['signal_strength'], latest_signal
    
    def execute_buy(self, symbol, price, signal_strength):
        """Execute a buy order (simulated)"""
        if symbol in self.portfolio['positions']:
            print(f"Already in position for {symbol}")
            return False
        
        investment = self.portfolio['cash'] * self.position_size
        if investment <= 0:
            print(f"Insufficient cash to buy {symbol}")
            return False
        
        quantity = investment / price
        
        # Update portfolio
        self.portfolio['positions'][symbol] = {
            'quantity': quantity,
            'entry_price': price,
            'entry_date': datetime.now()
        }
        self.portfolio['cash'] -= investment
        
        # Record trade in database
        self.db.insert_trade(
            symbol=symbol,
            trade_type='BUY',
            quantity=quantity,
            price=price,
            strategy='paper_trading',
            notes=f'Signal strength: {signal_strength:.0f}%'
        )
        
        # Record signal
        self.db.insert_signal(
            symbol=symbol,
            signal_type='BUY',
            indicator_name='combined',
            signal_strength=signal_strength,
            price=price
        )
        
        self.save_portfolio()
        
        print(f"\n{'='*70}")
        print(f"BUY ORDER EXECUTED")
        print(f"{'='*70}")
        print(f"Symbol: {symbol}")
        print(f"Price: ${price:,.2f}")
        print(f"Quantity: {quantity:.6f}")
        print(f"Investment: ${investment:,.2f}")
        print(f"Signal Strength: {signal_strength:.0f}%")
        print(f"Remaining Cash: ${self.portfolio['cash']:,.2f}")
        print(f"{'='*70}\n")
        
        return True
    
    def execute_sell(self, symbol, price, reason='SIGNAL', signal_strength=0):
        """Execute a sell order (simulated)"""
        if symbol not in self.portfolio['positions']:
            print(f"No position to sell for {symbol}")
            return False
        
        position = self.portfolio['positions'][symbol]
        quantity = position['quantity']
        entry_price = position['entry_price']
        
        sale_value = quantity * price
        profit_loss = sale_value - (quantity * entry_price)
        profit_loss_pct = ((price - entry_price) / entry_price) * 100
        
        # Update portfolio
        self.portfolio['cash'] += sale_value
        self.portfolio['total_profit_loss'] += profit_loss
        del self.portfolio['positions'][symbol]
        
        # Record trade in database
        self.db.insert_trade(
            symbol=symbol,
            trade_type='SELL',
            quantity=quantity,
            price=price,
            strategy='paper_trading',
            notes=f'Exit reason: {reason}, P/L: {profit_loss_pct:.2f}%'
        )
        
        # Record signal if it's a signal-based sell
        if reason == 'SIGNAL':
            self.db.insert_signal(
                symbol=symbol,
                signal_type='SELL',
                indicator_name='combined',
                signal_strength=signal_strength,
                price=price
            )
        
        self.save_portfolio()
        
        print(f"\n{'='*70}")
        print(f"SELL ORDER EXECUTED - {reason}")
        print(f"{'='*70}")
        print(f"Symbol: {symbol}")
        print(f"Entry Price: ${entry_price:,.2f}")
        print(f"Exit Price: ${price:,.2f}")
        print(f"Quantity: {quantity:.6f}")
        print(f"Sale Value: ${sale_value:,.2f}")
        print(f"Profit/Loss: ${profit_loss:,.2f} ({profit_loss_pct:+.2f}%)")
        print(f"New Cash Balance: ${self.portfolio['cash']:,.2f}")
        print(f"Total P/L: ${self.portfolio['total_profit_loss']:,.2f}")
        print(f"{'='*70}\n")
        
        return True
    
    def check_stop_loss_take_profit(self, symbol, current_price):
        """Check if stop loss or take profit should be triggered"""
        if symbol not in self.portfolio['positions']:
            return
        
        position = self.portfolio['positions'][symbol]
        entry_price = position['entry_price']
        
        price_change = (current_price - entry_price) / entry_price
        
        # Check stop loss
        if price_change <= -self.stop_loss:
            print(f"STOP LOSS TRIGGERED for {symbol}")
            self.execute_sell(symbol, current_price, reason='STOP_LOSS')
            return True
        
        # Check take profit
        if price_change >= self.take_profit:
            print(f"TAKE PROFIT TRIGGERED for {symbol}")
            self.execute_sell(symbol, current_price, reason='TAKE_PROFIT')
            return True
        
        return False
    
    def update_portfolio_value(self):
        """Calculate current total portfolio value"""
        total = self.portfolio['cash']
        
        for symbol, position in self.portfolio['positions'].items():
            current_price = self.fetch_current_price(symbol)
            if current_price:
                position_value = position['quantity'] * current_price
                total += position_value
        
        self.portfolio['total_value'] = total
    
    def print_portfolio_status(self):
        """Print current portfolio status"""
        self.update_portfolio_value()
        
        print(f"\n{'='*70}")
        print(f"PORTFOLIO STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        print(f"Cash: ${self.portfolio['cash']:,.2f}")
        print(f"Total Portfolio Value: ${self.portfolio['total_value']:,.2f}")
        print(f"Total P/L: ${self.portfolio['total_profit_loss']:,.2f}")
        print(f"Return: {((self.portfolio['total_value'] - self.initial_capital) / self.initial_capital * 100):+.2f}%")
        
        if self.portfolio['positions']:
            print(f"\nCurrent Positions:")
            for symbol, position in self.portfolio['positions'].items():
                current_price = self.fetch_current_price(symbol)
                if current_price:
                    position_value = position['quantity'] * current_price
                    unrealized_pl = position_value - (position['quantity'] * position['entry_price'])
                    unrealized_pl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
                    
                    print(f"  {symbol}:")
                    print(f"    Quantity: {position['quantity']:.6f}")
                    print(f"    Entry: ${position['entry_price']:,.2f}")
                    print(f"    Current: ${current_price:,.2f}")
                    print(f"    Value: ${position_value:,.2f}")
                    print(f"    Unrealized P/L: ${unrealized_pl:,.2f} ({unrealized_pl_pct:+.2f}%)")
        else:
            print("\nNo open positions")
        
        print(f"{'='*70}\n")
    
    def run_trading_cycle(self):
        """Run one trading cycle - check signals and execute trades"""
        self.last_cycle_time = datetime.now()
        print(f"\nRunning trading cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for symbol in self.symbols:
            print(f"\nAnalyzing {symbol}...")
            
            # Get current price
            current_price = self.fetch_current_price(symbol)
            if not current_price:
                print(f"Could not fetch price for {symbol}")
                continue
            
            print(f"Current price: ${current_price:,.2f}")
            
            # Check stop loss / take profit for existing positions
            if symbol in self.portfolio['positions']:
                if self.check_stop_loss_take_profit(symbol, current_price):
                    continue  # Position closed, move to next symbol
            
            # Generate trading signal
            signal, signal_strength, signal_details = self.generate_signal(symbol)

            # Store for the dashboard to read.
            self.last_signals[symbol] = {
                'signal': signal,
                'strength': float(signal_strength),
                'price': float(current_price),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"Signal: {signal} (Strength: {signal_strength:.0f}%)")
            
            # Execute trades based on signals
            if signal == 'BUY' and signal_strength >= 75:
                if symbol not in self.portfolio['positions']:
                    self.execute_buy(symbol, current_price, signal_strength)
            
            elif signal == 'SELL' and signal_strength >= 75:
                if symbol in self.portfolio['positions']:
                    self.execute_sell(symbol, current_price, reason='SIGNAL', signal_strength=signal_strength)
        
        # Print portfolio status
        self.print_portfolio_status()
    
    def start(self):
        """Start the paper trading bot"""
        self.is_running = True
        self._stop_event.clear()
        
        print("\n" + "="*70)
        print("PAPER TRADING BOT STARTED")
        print("="*70)
        print("Press Ctrl+C to stop")
        print("="*70 + "\n")
        
        try:
            while self.is_running:
                self.run_trading_cycle()
                
                print(f"Waiting {self.check_interval//60} minutes until next check...")
                # Interruptible wait: returns True immediately if stop() is
                # called, instead of blocking for the full check_interval.
                if self._stop_event.wait(self.check_interval):
                    break
                
        except KeyboardInterrupt:
            print("\n\nStopping paper trading bot...")
        finally:
            self.is_running = False
            self.save_portfolio()
            print("\n" + "="*70)
            print("PAPER TRADING BOT STOPPED")
            print("="*70)
            self.print_portfolio_status()
            print("Portfolio saved. You can resume later.")
            print("="*70 + "\n")
    
    def stop(self):
        """Stop the paper trading bot (interrupts the wait immediately)"""
        self.is_running = False
        self._stop_event.set()


# Run paper trading bot
if __name__ == "__main__":
    print("\n" + "="*70)
    print("PAPER TRADING BOT SETUP")
    print("="*70)
    
    # Configuration
    print("\nEnter configuration (press Enter for defaults):\n")
    
    symbols_input = input("Symbols (comma-separated, default: BTC-USD): ").strip()
    symbols = [s.strip() for s in symbols_input.split(',')] if symbols_input else ['BTC-USD']
    
    capital_input = input("Initial capital (default: $10,000): ").strip()
    initial_capital = float(capital_input) if capital_input else 10000
    
    pos_size_input = input("Position size % (default: 95): ").strip()
    position_size = float(pos_size_input) / 100 if pos_size_input else 0.95
    
    stop_loss_input = input("Stop loss % (default: 3): ").strip()
    stop_loss = float(stop_loss_input) / 100 if stop_loss_input else 0.03
    
    take_profit_input = input("Take profit % (default: 20): ").strip()
    take_profit = float(take_profit_input) / 100 if take_profit_input else 0.20
    
    interval_input = input("Check interval in minutes (default: 60): ").strip()
    check_interval = int(interval_input) * 60 if interval_input else 3600
    
    # Create and start bot
    bot = PaperTradingBot(
        symbols=symbols,
        initial_capital=initial_capital,
        position_size=position_size,
        stop_loss=stop_loss,
        take_profit=take_profit
    )
    
    bot.check_interval = check_interval
    
    # Start the bot
    bot.start()