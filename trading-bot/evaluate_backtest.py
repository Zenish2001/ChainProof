#!/usr/bin/env python3
"""
evaluate_backtest.py -- puts the backtest numbers in context

The headline backtest return answers "what did the best parameter set
earn on this history?". It leaves three questions open, and this script
answers them:

  1. BENCHMARK  Did the strategy beat simply buying and holding the asset
                over the same period?
  2. COSTS      What is left after trading fees and slippage?
  3. OUT OF     Does the parameter choice hold up on data it was not tuned
     SAMPLE     on? Parameters are chosen by grid search on the first part
                of the history (train) and then run, unchanged, on the
                rest (test).

The simulator below reproduces TradingStrategy.execute_backtest() exactly
when costs are zero -- tests/test_strategy.py checks this trade for trade
-- and adds two things the original does not have: a cost per side, and a
trading window, so indicators can be computed on the full history (they
only ever look backwards) while trades happen only inside the window.

Usage (from trading-bot/):
    python evaluate_backtest.py --db data/trading_bot.db
    python evaluate_backtest.py --csv ../verification-layer/fixtures/BTC-USD.csv
Options:
    --symbols BTC-USD ETH-USD   only these symbols (--db only)
    --cost 0.001                cost per side as a fraction (default 0.1%)
    --train-frac 0.7            share of the history used to choose parameters

Sharpe is annualised with sqrt(252) to stay comparable with the original
backtester. Crypto trades every day, so sqrt(365) is arguably more
appropriate; it would scale every Sharpe figure here by about 1.2.
"""

import argparse
import itertools
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE)

from indicators.technical_indicators import TechnicalIndicators  # noqa: E402
from price_data import list_symbols, load_prices_csv, load_prices_db  # noqa: E402

INITIAL_CAPITAL = 10000

# The same grid StrategyOptimizer searches: 3 x 4 x 4 = 48 combinations.
POSITION_SIZES = [0.9, 0.95, 1.0]
STOP_LOSSES = [0.03, 0.05, 0.07, 0.10]
TAKE_PROFITS = [0.10, 0.15, 0.20, 0.25]

OUTPUT_CSV = os.path.join(HERE, "..", "verification-layer", "results", "backtest_evaluation.csv")


# ---------------------------------------------------------------- simulator

def simulate(signals, position_size, stop_loss, take_profit, cost=0.0,
             initial_capital=INITIAL_CAPITAL):
    """Run the strategy's trading rules over `signals`.

    `signals` is the output of TechnicalIndicators.generate_signals(),
    optionally sliced to a trading window. The rules mirror
    TradingStrategy.execute_backtest() line for line: stop-loss is checked
    before take-profit, an exit bar never re-enters, entries and signal
    exits need signal_strength >= 50, and an open position is closed on the
    last bar. `cost` is charged on the traded value on every entry and exit.

    Returns (equity, trades, final_value). `equity` is the portfolio value
    at each bar before that bar's trades, as in the original.
    """
    capital = initial_capital
    position = 0.0
    in_position = False
    entry_price = 0.0
    entry_date = None
    entry_outlay = 0.0
    trades = []
    equity = []

    def close(date, price, reason):
        nonlocal capital, position, in_position
        proceeds = position * price * (1 - cost)
        capital += proceeds
        trades.append({
            "entry_date": entry_date,
            "exit_date": date,
            "entry_price": entry_price,
            "exit_price": price,
            "profit_loss": proceeds - entry_outlay,
            "profit_loss_pct": (price - entry_price) / entry_price * 100,
            "exit_reason": reason,
        })
        position = 0.0
        in_position = False

    for date, row in signals.iterrows():
        price = row["price"]
        signal = row["overall_signal"]
        strength = row["signal_strength"]

        equity.append(capital + position * price)

        if in_position:
            change = (price - entry_price) / entry_price
            if change <= -stop_loss:
                close(date, price, "STOP_LOSS")
                continue
            if change >= take_profit:
                close(date, price, "TAKE_PROFIT")
                continue

        if signal == "BUY" and not in_position and strength >= 50:
            investment = capital * position_size
            position = investment * (1 - cost) / price
            capital -= investment
            entry_outlay = investment
            entry_price = price
            entry_date = date
            in_position = True
        elif signal == "SELL" and in_position and strength >= 50:
            close(date, price, "SIGNAL")

    if in_position:
        close(signals.index[-1], signals.iloc[-1]["price"], "END_OF_DATA")

    return pd.Series(equity, index=signals.index), pd.DataFrame(trades), capital


# ------------------------------------------------------------------ metrics

def sharpe(values):
    returns = pd.Series(values).pct_change()
    std = returns.std()
    return float(returns.mean() / std * np.sqrt(252)) if std and std == std else 0.0


def max_drawdown_pct(values):
    values = pd.Series(values)
    return float(((values - values.cummax()) / values.cummax()).min() * 100)


def strategy_metrics(equity, trades, final_value, initial_capital=INITIAL_CAPITAL):
    n = len(trades)
    wins = int((trades["profit_loss"] > 0).sum()) if n else 0
    return {
        "return_pct": (final_value - initial_capital) / initial_capital * 100,
        "sharpe": sharpe(equity),
        "max_drawdown_pct": max_drawdown_pct(equity),
        "trades": n,
        "win_rate_pct": wins / n * 100 if n else 0.0,
    }


def buy_and_hold_metrics(prices):
    prices = pd.Series(prices)
    return {
        "return_pct": (prices.iloc[-1] / prices.iloc[0] - 1) * 100,
        "sharpe": sharpe(prices),
        "max_drawdown_pct": max_drawdown_pct(prices),
    }


# --------------------------------------------------------------- evaluation

def grid_search(signals, cost=0.0):
    """Best (position_size, stop_loss, take_profit) by total return."""
    best = None
    for pos, sl, tp in itertools.product(POSITION_SIZES, STOP_LOSSES, TAKE_PROFITS):
        equity, trades, final = simulate(signals, pos, sl, tp, cost)
        result = strategy_metrics(equity, trades, final)
        if best is None or result["return_pct"] > best[1]["return_pct"]:
            best = ((pos, sl, tp), result)
    return best


def evaluate(df, cost, train_frac):
    """Return a list of result rows for one symbol."""
    signals, _ = TechnicalIndicators.generate_signals(df)
    split = int(len(signals) * train_frac)
    train, test = signals.iloc[:split], signals.iloc[split:]

    rows = []

    def add(label, window, params, strat):
        bh = buy_and_hold_metrics(window["price"])
        rows.append({
            "run": label,
            "start": str(window.index[0].date()),
            "end": str(window.index[-1].date()),
            "position_size": params[0], "stop_loss": params[1], "take_profit": params[2],
            "strategy_return_pct": strat["return_pct"],
            "buy_hold_return_pct": bh["return_pct"],
            "excess_return_pct": strat["return_pct"] - bh["return_pct"],
            "strategy_sharpe": strat["sharpe"],
            "buy_hold_sharpe": bh["sharpe"],
            "strategy_max_dd_pct": strat["max_drawdown_pct"],
            "buy_hold_max_dd_pct": bh["max_drawdown_pct"],
            "trades": strat["trades"],
            "win_rate_pct": strat["win_rate_pct"],
        })

    # A. The original headline: best of 48 on the full history, no costs.
    full_params, full_result = grid_search(signals, cost=0.0)
    add("A. full history, best of 48, no costs", signals, full_params, full_result)

    # B. The same parameters after costs.
    add(f"B. same parameters, {cost:.2%} cost per side", signals, full_params,
        strategy_metrics(*simulate(signals, *full_params, cost=cost)))

    # C. Out of sample: choose on train (with costs), run unchanged on test.
    train_params, train_result = grid_search(train, cost=cost)
    add("C1. train window, best of 48, with costs", train, train_params, train_result)
    add("C2. test window, train's parameters, with costs", test, train_params,
        strategy_metrics(*simulate(test, *train_params, cost=cost)))

    return rows


def print_rows(symbol, rows):
    print()
    print("=" * 96)
    print(symbol)
    print("=" * 96)
    print(f"{'run':<50}{'window':<25}{'strategy':>10}{'buy&hold':>10}{'excess':>10}{'sharpe':>8}{'trades':>8}")
    for r in rows:
        window = f"{r['start']} to {r['end']}"
        print(f"{r['run']:<50}{window:<25}{r['strategy_return_pct']:>9.2f}%"
              f"{r['buy_hold_return_pct']:>9.2f}%{r['excess_return_pct']:>9.2f}%"
              f"{r['strategy_sharpe']:>8.2f}{r['trades']:>8}")
        print(f"{'':<50}parameters pos={r['position_size']} sl={r['stop_loss']} "
              f"tp={r['take_profit']}  max drawdown {r['strategy_max_dd_pct']:.1f}% "
              f"(buy & hold {r['buy_hold_max_dd_pct']:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--db", help="path to the bot's SQLite database")
    source.add_argument("--csv", help="path to a price fixture CSV")
    parser.add_argument("--symbols", nargs="*", help="symbols to evaluate (--db only)")
    parser.add_argument("--cost", type=float, default=0.001, help="cost per side (default 0.001)")
    parser.add_argument("--train-frac", type=float, default=0.7, help="train share (default 0.7)")
    args = parser.parse_args()

    if args.db:
        symbols = args.symbols or list_symbols(args.db)
        datasets = [(s, load_prices_db(args.db, s)) for s in symbols]
    else:
        name = os.path.splitext(os.path.basename(args.csv))[0]
        datasets = [(name, load_prices_csv(args.csv))]

    all_rows = []
    for symbol, df in datasets:
        rows = evaluate(df, args.cost, args.train_frac)
        print_rows(symbol, rows)
        all_rows += [{"symbol": symbol, **r} for r in rows]

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    pd.DataFrame(all_rows).to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved to {os.path.normpath(OUTPUT_CSV)}")
    print("Run A should reproduce strategy_comparison.csv. If it does not, the")
    print("price data differs from the data the original sweep ran on.")


if __name__ == "__main__":
    main()
