"""
generate_replay_data.py

Produces the real replay dataset ChainProof will verify on-chain.

This is NOT synthetic/seed data. It:
  1. Loads real historical BTC-USD price data from trading_bot.db
  2. Runs TechnicalIndicators.generate_signals() -- the exact, unmodified
     indicator/signal engine your bot uses live
  3. Runs TradingStrategy.execute_backtest() with the WINNING parameters
     from strategy_comparison.csv (position_size=0.95, stop_loss=0.03,
     take_profit=0.20 -- the run behind your +38.47%/Sharpe 0.64 numbers)
  4. Splits each closed trade into its two underlying DECISIONS (the BUY
     that opened it, the SELL/STOP_LOSS/TAKE_PROFIT that closed it) --
     because a "trading decision" is what ChainProof commits and verifies,
     not a closed round-trip trade
  5. For each decision, looks up the exact indicator snapshot that existed
     at that timestamp (price, signal strength, and every indicator column
     generate_signals() computed) -- these are the "inputs" the proposal
     commits to
  6. Saves the first ~30 decisions to CSV, ready for the commitment-hashing
     script

Run from the project root:
    python chainproof/generate_replay_data.py
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from data.database import TradingDatabase
from indicators.technical_indicators import TechnicalIndicators
from strategies.trading_strategy import TradingStrategy

# Winning parameters from data/strategy_comparison.csv -- the run behind
# the +38.47% / Sharpe 0.64 headline numbers.
SYMBOL = "BTC-USD"
POSITION_SIZE = 0.95
STOP_LOSS = 0.03
TAKE_PROFIT = 0.20
MAX_DECISIONS = 30  # matches the proposal's 20-30 trade replay scope

OUTPUT_PATH = "data/chainproof_replay_decisions.csv"


def main():
    print("=" * 70)
    print("CHAINPROOF -- GENERATING REPLAY DATASET FROM REAL BACKTEST")
    print("=" * 70)

    db = TradingDatabase()
    df = db.get_price_data(SYMBOL)

    if df.empty:
        print(f"No price data found for {SYMBOL}. Run historical_data_collector.py first.")
        return

    print(f"Loaded {len(df)} price records for {SYMBOL}")
    print(f"Range: {df.index[0]} to {df.index[-1]}")

    # Step 1: compute the full indicator/signal snapshot for every timestamp.
    # This is the exact same call execute_backtest() makes internally --
    # we call it directly too so we can look up the indicator values at
    # each individual decision point afterward.
    signals, df_with_indicators = TechnicalIndicators.generate_signals(df)
    print(f"Computed indicators/signals for {len(signals)} timestamps")

    # Step 2: run the actual backtest with the winning parameters.
    strategy = TradingStrategy(
        initial_capital=10000,
        position_size=POSITION_SIZE,
        stop_loss=STOP_LOSS,
        take_profit=TAKE_PROFIT,
    )
    trades_df, portfolio_df, performance = strategy.execute_backtest(df, SYMBOL)

    print(f"\nBacktest complete:")
    print(f"  Total closed trades: {performance['total_trades']}")
    print(f"  Total return: {performance['total_return_pct']:.2f}%")
    print(f"  Sharpe ratio: {performance['sharpe_ratio']:.2f}")
    print(f"  Win rate: {performance['win_rate']:.2f}%")

    if len(trades_df) == 0:
        print("No trades were generated -- nothing to replay.")
        return

    # Step 3: split each closed trade into its two underlying decisions,
    # and attach the real indicator snapshot at that exact timestamp.
    decisions = []

    for _, trade in trades_df.iterrows():
        for role, date_col, price_col, action in [
            ("ENTRY", "entry_date", "entry_price", "BUY"),
            ("EXIT", "exit_date", "exit_price", "SELL"),
        ]:
            ts = trade[date_col]
            price = trade[price_col]

            if ts not in signals.index:
                continue

            snapshot = signals.loc[ts]

            decision = {
                "timestamp": ts,
                "role": role,
                "action": action if role == "ENTRY" else trade["exit_reason"],
                "price": price,
                "signal_strength": snapshot.get("signal_strength"),
                "overall_signal": snapshot.get("overall_signal"),
            }

            for col in signals.columns:
                if col not in ("price", "signal_strength", "overall_signal"):
                    decision[f"ind_{col}"] = snapshot.get(col)

            decisions.append(decision)

    decisions_df = pd.DataFrame(decisions)
    decisions_df = decisions_df.sort_values("timestamp").reset_index(drop=True)

    if len(decisions_df) > MAX_DECISIONS:
        decisions_df = decisions_df.head(MAX_DECISIONS)
        print(f"\nTrimmed to first {MAX_DECISIONS} decisions (proposal's 20-30 trade scope)")

    print(f"\nCaptured {len(decisions_df)} individual trading decisions")
    print("\nPreview:")
    print(decisions_df[["timestamp", "role", "action", "price", "signal_strength"]].head(10).to_string())

    os.makedirs("data", exist_ok=True)
    decisions_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved to: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
