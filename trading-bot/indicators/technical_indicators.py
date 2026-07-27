import pandas as pd
import numpy as np

class TechnicalIndicators:
    """
    Calculate technical indicators for trading signals
    """
    
    @staticmethod
    def calculate_sma(df, period=20, column='close'):
        """
        Calculate Simple Moving Average
        """
        return df[column].rolling(window=period).mean()
    
    @staticmethod
    def calculate_ema(df, period=20, column='close'):
        """
        Calculate Exponential Moving Average
        """
        return df[column].ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(df, period=14, column='close'):
        """
        Calculate Relative Strength Index (RSI)
        RSI > 70 = Overbought
        RSI < 30 = Oversold
        """
        delta = df[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(df, fast=12, slow=26, signal=9, column='close'):
        """
        Calculate MACD (Moving Average Convergence Divergence)
        Returns: macd_line, signal_line, histogram
        """
        exp1 = df[column].ewm(span=fast, adjust=False).mean()
        exp2 = df[column].ewm(span=slow, adjust=False).mean()
        
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(df, period=20, std_dev=2, column='close'):
        """
        Calculate Bollinger Bands
        Returns: upper_band, middle_band, lower_band
        """
        middle_band = df[column].rolling(window=period).mean()
        std = df[column].rolling(window=period).std()
        
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def calculate_stochastic(df, period=14):
        """
        Calculate Stochastic Oscillator
        Returns: %K, %D
        """
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()
        
        k_percent = 100 * ((df['close'] - low_min) / (high_max - low_min))
        d_percent = k_percent.rolling(window=3).mean()
        
        return k_percent, d_percent
    
    @staticmethod
    def calculate_atr(df, period=14):
        """
        Calculate Average True Range (ATR) - Volatility indicator
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr
    
    @staticmethod
    def calculate_obv(df):
        """
        Calculate On-Balance Volume (OBV)
        """
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return obv
    
    @staticmethod
    def add_all_indicators(df):
        """
        Add all technical indicators to a DataFrame
        """
        df_copy = df.copy()
        
        # Moving Averages
        df_copy['sma_20'] = TechnicalIndicators.calculate_sma(df_copy, 20)
        df_copy['sma_50'] = TechnicalIndicators.calculate_sma(df_copy, 50)
        df_copy['sma_200'] = TechnicalIndicators.calculate_sma(df_copy, 200)
        df_copy['ema_12'] = TechnicalIndicators.calculate_ema(df_copy, 12)
        df_copy['ema_26'] = TechnicalIndicators.calculate_ema(df_copy, 26)
        
        # RSI
        df_copy['rsi'] = TechnicalIndicators.calculate_rsi(df_copy)
        
        # MACD
        macd, signal, hist = TechnicalIndicators.calculate_macd(df_copy)
        df_copy['macd'] = macd
        df_copy['macd_signal'] = signal
        df_copy['macd_hist'] = hist
        
        # Bollinger Bands
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(df_copy)
        df_copy['bb_upper'] = upper
        df_copy['bb_middle'] = middle
        df_copy['bb_lower'] = lower
        
        # Stochastic
        k, d = TechnicalIndicators.calculate_stochastic(df_copy)
        df_copy['stoch_k'] = k
        df_copy['stoch_d'] = d
        
        # ATR (Volatility)
        df_copy['atr'] = TechnicalIndicators.calculate_atr(df_copy)
        
        # OBV (Volume)
        df_copy['obv'] = TechnicalIndicators.calculate_obv(df_copy)
        
        return df_copy
    
    @staticmethod
    def generate_signals(df):
        """
        Generate trading signals based on indicators
        Returns DataFrame with buy/sell/hold signals
        """
        df_with_indicators = TechnicalIndicators.add_all_indicators(df)
        
        signals = pd.DataFrame(index=df_with_indicators.index)
        signals['price'] = df_with_indicators['close']
        
        # Initialize signal columns
        signals['rsi_signal'] = 'HOLD'
        signals['macd_signal'] = 'HOLD'
        signals['ma_signal'] = 'HOLD'
        signals['bb_signal'] = 'HOLD'
        signals['overall_signal'] = 'HOLD'
        
        # RSI Signals
        signals.loc[df_with_indicators['rsi'] < 30, 'rsi_signal'] = 'BUY'
        signals.loc[df_with_indicators['rsi'] > 70, 'rsi_signal'] = 'SELL'
        
        # MACD Signals
        signals.loc[df_with_indicators['macd'] > df_with_indicators['macd_signal'], 'macd_signal'] = 'BUY'
        signals.loc[df_with_indicators['macd'] < df_with_indicators['macd_signal'], 'macd_signal'] = 'SELL'
        
        # Moving Average Crossover
        signals.loc[df_with_indicators['sma_20'] > df_with_indicators['sma_50'], 'ma_signal'] = 'BUY'
        signals.loc[df_with_indicators['sma_20'] < df_with_indicators['sma_50'], 'ma_signal'] = 'SELL'
        
        # Bollinger Bands
        signals.loc[df_with_indicators['close'] < df_with_indicators['bb_lower'], 'bb_signal'] = 'BUY'
        signals.loc[df_with_indicators['close'] > df_with_indicators['bb_upper'], 'bb_signal'] = 'SELL'
        
        # Overall signal (majority vote)
        buy_count = (signals[['rsi_signal', 'macd_signal', 'ma_signal', 'bb_signal']] == 'BUY').sum(axis=1)
        sell_count = (signals[['rsi_signal', 'macd_signal', 'ma_signal', 'bb_signal']] == 'SELL').sum(axis=1)
        
        signals.loc[buy_count >= 2, 'overall_signal'] = 'BUY'
        signals.loc[sell_count >= 2, 'overall_signal'] = 'SELL'
        
        # Signal strength (0-100)
        signals['signal_strength'] = 0
        signals.loc[signals['overall_signal'] == 'BUY', 'signal_strength'] = (buy_count / 4 * 100).loc[signals['overall_signal'] == 'BUY']
        signals.loc[signals['overall_signal'] == 'SELL', 'signal_strength'] = (sell_count / 4 * 100).loc[signals['overall_signal'] == 'SELL']
        
        return signals, df_with_indicators


# Test the indicators
if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data.database import TradingDatabase
    
    print("\nTesting Technical Indicators...\n")
    print("=" * 60)
    
    db = TradingDatabase()
    
    # Get BTC data
    symbol = 'BTC-USD'
    df = db.get_price_data(symbol)
    
    if df.empty:
        print(f"No data found for {symbol}")
        print("Please run historical_data_collector.py first")
    else:
        print(f"Loaded {len(df)} records for {symbol}")
        print(f"Date range: {df.index[0]} to {df.index[-1]}")
        
        # Add all indicators
        print("\nCalculating indicators...")
        df_with_indicators = TechnicalIndicators.add_all_indicators(df)
        
        # Show latest values
        print("\nLatest Indicator Values:")
        print("-" * 60)
        latest = df_with_indicators.iloc[-1]
        print(f"Price: ${latest['close']:.2f}")
        print(f"RSI (14): {latest['rsi']:.2f}")
        print(f"MACD: {latest['macd']:.2f}")
        print(f"MACD Signal: {latest['macd_signal']:.2f}")
        print(f"SMA 20: ${latest['sma_20']:.2f}")
        print(f"SMA 50: ${latest['sma_50']:.2f}")
        print(f"Bollinger Upper: ${latest['bb_upper']:.2f}")
        print(f"Bollinger Lower: ${latest['bb_lower']:.2f}")
        
        # Generate signals
        print("\nGenerating trading signals...")
        signals, _ = TechnicalIndicators.generate_signals(df)
        
        # Show recent signals
        print("\nRecent Trading Signals:")
        print("-" * 60)
        recent_signals = signals.tail(5)
        for idx, row in recent_signals.iterrows():
            print(f"{idx}: {row['overall_signal']} (Strength: {row['signal_strength']:.0f}%) @ ${row['price']:.2f}")
        
        print("\n" + "=" * 60)
        print("Indicators calculated successfully!")