import pandas as pd
import numpy as np
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.technical_indicators import TechnicalIndicators

class TradingStrategy:
    """
    Trading strategy that uses technical indicators to make buy/sell decisions
    """
    
    def __init__(self, initial_capital=10000, position_size=0.95, stop_loss=0.05, take_profit=0.15):
        """
        Initialize trading strategy
        
        Parameters:
        - initial_capital: Starting capital in USD
        - position_size: Percentage of capital to use per trade (0.95 = 95%)
        - stop_loss: Stop loss percentage (0.05 = 5%)
        - take_profit: Take profit percentage (0.15 = 15%)
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
    def execute_backtest(self, df, symbol='BTC-USD'):
        """
        Backtest the trading strategy on historical data
        
        Returns:
        - trades_df: DataFrame with all trades
        - performance: Dictionary with performance metrics
        """
        # Get signals
        signals, df_with_indicators = TechnicalIndicators.generate_signals(df)
        
        # Initialize portfolio
        capital = self.initial_capital
        position = 0  # Amount of crypto held
        position_value = 0
        trades = []
        portfolio_values = []
        
        in_position = False
        entry_price = 0
        entry_date = None
        
        # Iterate through data
        for date, row in signals.iterrows():
            current_price = row['price']
            signal = row['overall_signal']
            signal_strength = row['signal_strength']
            
            # Calculate current portfolio value
            current_value = capital + (position * current_price)
            portfolio_values.append({
                'date': date,
                'portfolio_value': current_value,
                'capital': capital,
                'position': position,
                'price': current_price
            })
            
            # Check stop loss and take profit if in position
            if in_position:
                price_change = (current_price - entry_price) / entry_price
                
                # Stop Loss
                if price_change <= -self.stop_loss:
                    # SELL - Stop Loss Hit
                    sell_value = position * current_price
                    capital += sell_value
                    
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'quantity': position,
                        'profit_loss': sell_value - (position * entry_price),
                        'profit_loss_pct': price_change * 100,
                        'exit_reason': 'STOP_LOSS'
                    })
                    
                    position = 0
                    in_position = False
                    continue
                
                # Take Profit
                if price_change >= self.take_profit:
                    # SELL - Take Profit Hit
                    sell_value = position * current_price
                    capital += sell_value
                    
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'quantity': position,
                        'profit_loss': sell_value - (position * entry_price),
                        'profit_loss_pct': price_change * 100,
                        'exit_reason': 'TAKE_PROFIT'
                    })
                    
                    position = 0
                    in_position = False
                    continue
            
            # Trading logic based on signals
            if signal == 'BUY' and not in_position and signal_strength >= 50:
                # BUY signal
                investment = capital * self.position_size
                position = investment / current_price
                capital -= investment
                entry_price = current_price
                entry_date = date
                in_position = True
                
            elif signal == 'SELL' and in_position and signal_strength >= 50:
                # SELL signal
                sell_value = position * current_price
                capital += sell_value
                
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'quantity': position,
                    'profit_loss': sell_value - (position * entry_price),
                    'profit_loss_pct': ((current_price - entry_price) / entry_price) * 100,
                    'exit_reason': 'SIGNAL'
                })
                
                position = 0
                in_position = False
        
        # Close any open position at the end
        if in_position:
            final_price = signals.iloc[-1]['price']
            sell_value = position * final_price
            capital += sell_value
            
            trades.append({
                'entry_date': entry_date,
                'exit_date': signals.index[-1],
                'entry_price': entry_price,
                'exit_price': final_price,
                'quantity': position,
                'profit_loss': sell_value - (position * entry_price),
                'profit_loss_pct': ((final_price - entry_price) / entry_price) * 100,
                'exit_reason': 'END_OF_DATA'
            })
        
        # Create DataFrames
        trades_df = pd.DataFrame(trades)
        portfolio_df = pd.DataFrame(portfolio_values)
        
        # Calculate performance metrics
        if len(trades_df) > 0:
            performance = self.calculate_performance(trades_df, portfolio_df)
        else:
            performance = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit_loss': 0,
                'total_return_pct': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0
            }
        
        return trades_df, portfolio_df, performance
    
    def calculate_performance(self, trades_df, portfolio_df):
        """
        Calculate performance metrics
        """
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['profit_loss'] > 0])
        losing_trades = len(trades_df[trades_df['profit_loss'] < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_profit_loss = trades_df['profit_loss'].sum()
        final_value = portfolio_df.iloc[-1]['portfolio_value']
        total_return_pct = ((final_value - self.initial_capital) / self.initial_capital) * 100
        
        # Calculate max drawdown
        portfolio_df['cummax'] = portfolio_df['portfolio_value'].cummax()
        portfolio_df['drawdown'] = (portfolio_df['portfolio_value'] - portfolio_df['cummax']) / portfolio_df['cummax']
        max_drawdown = portfolio_df['drawdown'].min() * 100
        
        # Calculate Sharpe Ratio (simplified)
        portfolio_df['returns'] = portfolio_df['portfolio_value'].pct_change()
        sharpe_ratio = (portfolio_df['returns'].mean() / portfolio_df['returns'].std() * np.sqrt(252)) if portfolio_df['returns'].std() != 0 else 0
        
        # Average profit per trade
        avg_profit = trades_df['profit_loss'].mean()
        avg_profit_pct = trades_df['profit_loss_pct'].mean()
        
        # Best and worst trades
        best_trade = trades_df['profit_loss'].max() if total_trades > 0 else 0
        worst_trade = trades_df['profit_loss'].min() if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_profit_loss': total_profit_loss,
            'total_return_pct': total_return_pct,
            'final_portfolio_value': final_value,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'avg_profit': avg_profit,
            'avg_profit_pct': avg_profit_pct,
            'best_trade': best_trade,
            'worst_trade': worst_trade
        }
    
    def print_performance_report(self, symbol, performance, trades_df):
        """
        Print a formatted performance report
        """
        print("\n" + "="*70)
        print(f"BACKTEST RESULTS FOR {symbol}")
        print("="*70)
        
        print(f"\nInitial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Portfolio Value: ${performance['final_portfolio_value']:,.2f}")
        print(f"Total Return: ${performance['total_profit_loss']:,.2f} ({performance['total_return_pct']:.2f}%)")
        
        print(f"\nTrading Statistics:")
        print(f"  Total Trades: {performance['total_trades']}")
        print(f"  Winning Trades: {performance['winning_trades']}")
        print(f"  Losing Trades: {performance['losing_trades']}")
        print(f"  Win Rate: {performance['win_rate']:.2f}%")
        
        print(f"\nProfit Metrics:")
        print(f"  Average Profit per Trade: ${performance['avg_profit']:,.2f} ({performance['avg_profit_pct']:.2f}%)")
        print(f"  Best Trade: ${performance['best_trade']:,.2f}")
        print(f"  Worst Trade: ${performance['worst_trade']:,.2f}")
        
        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown: {performance['max_drawdown']:.2f}%")
        print(f"  Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
        
        if len(trades_df) > 0:
            print(f"\nRecent Trades (Last 5):")
            print("-" * 70)
            recent_trades = trades_df.tail(5)
            for idx, trade in recent_trades.iterrows():
                print(f"  {trade['entry_date'].strftime('%Y-%m-%d')} -> {trade['exit_date'].strftime('%Y-%m-%d')}")
                print(f"    Entry: ${trade['entry_price']:.2f} | Exit: ${trade['exit_price']:.2f}")
                print(f"    P/L: ${trade['profit_loss']:.2f} ({trade['profit_loss_pct']:.2f}%) | Reason: {trade['exit_reason']}")
                print()
        
        print("="*70 + "\n")


# Test the strategy
if __name__ == "__main__":
    from data.database import TradingDatabase
    
    print("\nTesting Trading Strategy with Backtesting...\n")
    
    db = TradingDatabase()
    
    # Test on BTC
    symbol = 'BTC-USD'
    df = db.get_price_data(symbol)
    
    if df.empty:
        print(f"No data found for {symbol}")
        print("Please run historical_data_collector.py first")
    else:
        print(f"Running backtest on {symbol}...")
        print(f"Data: {len(df)} records from {df.index[0]} to {df.index[-1]}\n")
        
        # Initialize strategy
        strategy = TradingStrategy(
            initial_capital=10000,
            position_size=0.95,
            stop_loss=0.05,
            take_profit=0.15
        )
        
        # Run backtest
        trades_df, portfolio_df, performance = strategy.execute_backtest(df, symbol)
        
        # Print report
        strategy.print_performance_report(symbol, performance, trades_df)
        
        # Test on other symbols
        for test_symbol in ['ETH-USD', 'SOL-USD']:
            df = db.get_price_data(test_symbol)
            if not df.empty:
                trades_df, portfolio_df, performance = strategy.execute_backtest(df, test_symbol)
                strategy.print_performance_report(test_symbol, performance, trades_df)