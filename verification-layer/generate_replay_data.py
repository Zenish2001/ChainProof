"""
generate_replay_data.py

Produces the real replay dataset ChainProof verifies on-chain.

This is NOT synthetic/seed data. It:
  1. Loads real historical BTC-USD price data from the bot's database
  2. Runs TechnicalIndicators.generate_signals() -- the exact, unmodified
     indicator/signal engine the bot uses
  3. Runs TradingStrategy.execute_backtest() with the winning parameters
     from strategy_comparison.csv (position_size=0.95, stop_loss=0.03,
     take_profit=0.20 -- the run behind the +38.47% / Sharpe 0.64 numbers)
  4. Splits each closed trade into its two underlying DECISIONS (the BUY
     that opened it, the SELL/STOP_LOSS/TAKE_PROFIT that closed it) --
     because a "trading decision" is what ChainProof commits and verifies,
     not a closed round-trip trade
  5. For each decision, looks up the exact signal snapshot that existed
     at that timestamp (price, signal strength, and each voting indicator's
     BUY/SELL/HOLD signal from generate_signals())
  6. Saves the first 30 decisions to CSV, ready for the commitment-hashing
     script

The decision-building logic lives in build_decisions(), which takes any
price DataFrame. replay_check.py calls the same function on the committed
price fixture, so the published decisions can be re-derived from raw
prices without the database.

Run from verification-layer/ (needs trading-bot/data/database.py and the
bot's SQLite database on your machine):
    python generate_replay_data.py
"""

import sys
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "trading-bot"))

from indicators.technical_indicators import TechnicalIndicators  # noqa: E402
from strategies.trading_strategy import TradingStrategy  # noqa: E402

# Winning parameters from results/strategy_comparison.csv -- the run behind
# the +38.47% / Sharpe 0.64 headline numbers.
SYMBOL = "BTC-USD"
POSITION_SIZE = 0.95
STOP_LOSS = 0.03
TAKE_PROFIT = 0.20
MAX_DECISIONS = 30  # matches the proposal's 20-30 trade replay scope

OUTPUT_PATH = os.path.join(HERE, "results", "chainproof_replay_decisions.csv")


def build_decisions(df, symbol=SYMBOL, max_decisions=MAX_DECISIONS):
    """Run the backtest on `df` and return (decisions_df, performance).

    `df` is a price DataFrame indexed by timestamp with open, high, low,
    close and volume columns -- the shape TradingDatabase.get_price_data()
    returns.
    """
    # Step 1: the full signal snapshot for every timestamp. This is the
    # same call execute_backtest() makes internally; it is made here too so
    # each decision's snapshot can be looked up afterwards.
    signals, _df_with_indicators = TechnicalIndicators.generate_signals(df)

    # Step 2: the actual backtest with the winning parameters.
    strategy = TradingStrategy(
        initial_capital=10000,
        position_size=POSITION_SIZE,
        stop_loss=STOP_LOSS,
        take_profit=TAKE_PROFIT,
    )
    trades_df, _portfolio_df, performance = strategy.execute_backtest(df, symbol)

    if len(trades_df) == 0:
        return pd.DataFrame(), performance

    # Step 3: split each closed trade into its two underlying decisions,
    # and attach the signal snapshot at that exact timestamp.
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

    if len(decisions_df) > max_decisions:
        decisions_df = decisions_df.head(max_decisions)

    return decisions_df, performance


def main():
    try:
        from data.database import TradingDatabase
    except ImportError:
        sys.exit("trading-bot/data/database.py is not in this repository, so the "
                 "database path cannot run from a clean clone. Use replay_check.py, "
                 "which re-derives the decisions from the committed price fixture.")

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

    decisions_df, performance = build_decisions(df)

    print("\nBacktest complete:")
    print(f"  Total closed trades: {performance['total_trades']}")
    print(f"  Total return: {performance['total_return_pct']:.2f}%")
    print(f"  Sharpe ratio: {performance['sharpe_ratio']:.2f}")
    print(f"  Win rate: {performance['win_rate']:.2f}%")

    if decisions_df.empty:
        print("No trades were generated -- nothing to replay.")
        return

    print(f"\nCaptured {len(decisions_df)} individual trading decisions "
          f"(first {MAX_DECISIONS} kept)")
    print("\nPreview:")
    print(decisions_df[["timestamp", "role", "action", "price", "signal_strength"]].head(10).to_string())

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    decisions_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved to: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
