import pandas as pd
import numpy as np
from itertools import product
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.database import TradingDatabase
from strategies.trading_strategy import TradingStrategy

class StrategyOptimizer:
    """
    Optimize trading strategy parameters through backtesting
    """
    
    def __init__(self):
        self.db = TradingDatabase()
        self.results = []
    
    def optimize_parameters(self, df, symbol, 
                           initial_capital=10000,
                           test_position_sizes=[0.9, 0.95, 1.0],
                           test_stop_losses=[0.03, 0.05, 0.07, 0.10],
                           test_take_profits=[0.10, 0.15, 0.20, 0.25]):
        """
        Test different parameter combinations to find optimal settings
        """
        print("\n" + "="*70)
        print(f"OPTIMIZING STRATEGY FOR {symbol}")
        print("="*70)
        print(f"\nTesting {len(test_position_sizes)} position sizes")
        print(f"Testing {len(test_stop_losses)} stop loss levels")
        print(f"Testing {len(test_take_profits)} take profit levels")
        
        total_combinations = len(test_position_sizes) * len(test_stop_losses) * len(test_take_profits)
        print(f"Total combinations to test: {total_combinations}")
        print("\nRunning backtests...\n")
        
        results = []
        test_count = 0
        
        # Test all combinations
        for pos_size in test_position_sizes:
            for stop_loss in test_stop_losses:
                for take_profit in test_take_profits:
                    test_count += 1
                    
                    # Create strategy with these parameters
                    strategy = TradingStrategy(
                        initial_capital=initial_capital,
                        position_size=pos_size,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                    
                    # Run backtest
                    trades_df, portfolio_df, performance = strategy.execute_backtest(df, symbol)
                    
                    # Store results
                    result = {
                        'symbol': symbol,
                        'position_size': pos_size,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'total_return_pct': performance['total_return_pct'],
                        'total_trades': performance['total_trades'],
                        'win_rate': performance['win_rate'],
                        'sharpe_ratio': performance['sharpe_ratio'],
                        'max_drawdown': performance['max_drawdown'],
                        'avg_profit_pct': performance['avg_profit_pct'],
                        'final_value': performance['final_portfolio_value']
                    }
                    results.append(result)
                    
                    # Progress update
                    if test_count % 10 == 0:
                        print(f"Completed {test_count}/{total_combinations} tests...")
        
        print(f"\nCompleted all {total_combinations} backtests!")
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        
        return results_df
    
    def find_best_parameters(self, results_df, metric='total_return_pct'):
        """
        Find the best parameter combination based on a specific metric
        
        Metrics:
        - total_return_pct: Highest return
        - sharpe_ratio: Best risk-adjusted return
        - win_rate: Highest win percentage
        - max_drawdown: Lowest drawdown (risk)
        """
        if metric == 'max_drawdown':
            # For drawdown, we want the highest (least negative) value
            best_idx = results_df[metric].idxmax()
        else:
            best_idx = results_df[metric].idxmax()
        
        best_params = results_df.loc[best_idx]
        return best_params
    
    def print_optimization_report(self, results_df, symbol):
        """
        Print detailed optimization results
        """
        print("\n" + "="*70)
        print(f"OPTIMIZATION RESULTS FOR {symbol}")
        print("="*70)
        
        # Overall statistics
        print(f"\nTotal tests run: {len(results_df)}")
        print(f"Average return: {results_df['total_return_pct'].mean():.2f}%")
        print(f"Best return: {results_df['total_return_pct'].max():.2f}%")
        print(f"Worst return: {results_df['total_return_pct'].min():.2f}%")
        
        # Best parameters by different metrics
        print("\n" + "-"*70)
        print("BEST PARAMETERS BY METRIC:")
        print("-"*70)
        
        metrics = {
            'total_return_pct': 'Highest Return',
            'sharpe_ratio': 'Best Risk-Adjusted Return (Sharpe)',
            'win_rate': 'Highest Win Rate',
            'max_drawdown': 'Lowest Risk (Max Drawdown)'
        }
        
        for metric, description in metrics.items():
            print(f"\n{description}:")
            best = self.find_best_parameters(results_df, metric)
            print(f"  Position Size: {best['position_size']*100:.0f}%")
            print(f"  Stop Loss: {best['stop_loss']*100:.0f}%")
            print(f"  Take Profit: {best['take_profit']*100:.0f}%")
            print(f"  Return: {best['total_return_pct']:.2f}%")
            print(f"  Win Rate: {best['win_rate']:.2f}%")
            print(f"  Sharpe Ratio: {best['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {best['max_drawdown']:.2f}%")
            print(f"  Total Trades: {int(best['total_trades'])}")
        
        # Top 5 overall performers
        print("\n" + "-"*70)
        print("TOP 5 STRATEGIES BY RETURN:")
        print("-"*70)
        
        top_5 = results_df.nlargest(5, 'total_return_pct')
        for idx, row in top_5.iterrows():
            print(f"\n#{idx+1}:")
            print(f"  Params: PosSize={row['position_size']*100:.0f}%, "
                  f"StopLoss={row['stop_loss']*100:.0f}%, "
                  f"TakeProfit={row['take_profit']*100:.0f}%")
            print(f"  Return: {row['total_return_pct']:.2f}% | "
                  f"Win Rate: {row['win_rate']:.2f}% | "
                  f"Sharpe: {row['sharpe_ratio']:.2f}")
        
        print("\n" + "="*70)
    
    def compare_strategies(self, symbols=['BTC-USD', 'ETH-USD', 'SOL-USD']):
        """
        Compare optimized strategies across multiple cryptocurrencies
        """
        print("\n" + "="*70)
        print("COMPARING STRATEGIES ACROSS CRYPTOCURRENCIES")
        print("="*70)
        
        comparison_results = []
        
        for symbol in symbols:
            print(f"\nLoading data for {symbol}...")
            df = self.db.get_price_data(symbol)
            
            if df.empty:
                print(f"No data available for {symbol}")
                continue
            
            # Quick optimization with fewer parameters for comparison
            results_df = self.optimize_parameters(
                df, symbol,
                test_position_sizes=[0.95],
                test_stop_losses=[0.03, 0.05, 0.07],
                test_take_profits=[0.10, 0.15, 0.20]
            )
            
            # Get best parameters
            best = self.find_best_parameters(results_df, 'total_return_pct')
            
            comparison_results.append({
                'symbol': symbol,
                'best_return': best['total_return_pct'],
                'position_size': best['position_size'],
                'stop_loss': best['stop_loss'],
                'take_profit': best['take_profit'],
                'win_rate': best['win_rate'],
                'sharpe_ratio': best['sharpe_ratio']
            })
        
        # Print comparison
        comparison_df = pd.DataFrame(comparison_results)
        
        print("\n" + "-"*70)
        print("COMPARISON SUMMARY:")
        print("-"*70)
        
        for idx, row in comparison_df.iterrows():
            print(f"\n{row['symbol']}:")
            print(f"  Best Return: {row['best_return']:.2f}%")
            print(f"  Optimal Stop Loss: {row['stop_loss']*100:.0f}%")
            print(f"  Optimal Take Profit: {row['take_profit']*100:.0f}%")
            print(f"  Win Rate: {row['win_rate']:.2f}%")
            print(f"  Sharpe Ratio: {row['sharpe_ratio']:.2f}")
        
        print("\n" + "="*70)
        
        return comparison_df
    
    def save_results(self, results_df, filename='optimization_results.csv'):
        """
        Save optimization results to CSV file
        """
        filepath = f'data/{filename}'
        results_df.to_csv(filepath, index=False)
        print(f"\nResults saved to: {filepath}")


# Run optimization
if __name__ == "__main__":
    print("\nStrategy Optimizer\n")
    
    optimizer = StrategyOptimizer()
    
    # Choose what to optimize
    print("Select optimization mode:")
    print("1. Full optimization (single crypto, all parameters)")
    print("2. Quick optimization (single crypto, limited parameters)")
    print("3. Compare across all cryptos (quick)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        # Full optimization on BTC
        symbol = 'BTC-USD'
        df = optimizer.db.get_price_data(symbol)
        
        if df.empty:
            print(f"No data found for {symbol}")
        else:
            results_df = optimizer.optimize_parameters(
                df, symbol,
                test_position_sizes=[0.9, 0.95, 1.0],
                test_stop_losses=[0.03, 0.05, 0.07, 0.10],
                test_take_profits=[0.10, 0.15, 0.20, 0.25, 0.30]
            )
            
            optimizer.print_optimization_report(results_df, symbol)
            optimizer.save_results(results_df, f'{symbol}_optimization.csv')
    
    elif choice == '2':
        # Quick optimization
        symbol = input("Enter symbol (BTC-USD, ETH-USD, SOL-USD): ").strip()
        df = optimizer.db.get_price_data(symbol)
        
        if df.empty:
            print(f"No data found for {symbol}")
        else:
            results_df = optimizer.optimize_parameters(
                df, symbol,
                test_position_sizes=[0.95],
                test_stop_losses=[0.03, 0.05, 0.07],
                test_take_profits=[0.10, 0.15, 0.20]
            )
            
            optimizer.print_optimization_report(results_df, symbol)
            optimizer.save_results(results_df, f'{symbol}_quick_optimization.csv')
    
    elif choice == '3':
        # Compare across all cryptos
        comparison_df = optimizer.compare_strategies()
        optimizer.save_results(comparison_df, 'strategy_comparison.csv')
    
    else:
        print("Invalid choice!")
    
    print("\nOptimization complete!")