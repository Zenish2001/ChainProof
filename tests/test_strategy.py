"""Tests for the trading-bot strategy and the backtest evaluator.

Run from the repository root:  pytest tests
"""

import itertools
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "trading-bot"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluate_backtest import buy_and_hold_metrics, simulate, strategy_metrics  # noqa: E402
from indicators.technical_indicators import TechnicalIndicators  # noqa: E402
from strategies.trading_strategy import TradingStrategy  # noqa: E402
from synthetic import synthetic_prices  # noqa: E402

VOTERS = ["rsi_signal", "macd_signal", "ma_signal", "bb_signal"]


def test_overall_signal_is_two_of_four_vote_with_sell_winning_ties():
    signals, _ = TechnicalIndicators.generate_signals(synthetic_prices())
    buys = (signals[VOTERS] == "BUY").sum(axis=1)
    sells = (signals[VOTERS] == "SELL").sum(axis=1)

    expected = np.where(sells >= 2, "SELL", np.where(buys >= 2, "BUY", "HOLD"))
    assert list(signals["overall_signal"]) == list(expected)

    ties = (buys == 2) & (sells == 2)
    assert ties.any(), "synthetic data should contain at least one 2-2 tie"
    assert (signals.loc[ties, "overall_signal"] == "SELL").all()


def test_signal_strength_is_agreeing_votes_out_of_four():
    signals, _ = TechnicalIndicators.generate_signals(synthetic_prices())
    for _, row in signals.iterrows():
        votes = sum(row[v] == row["overall_signal"] for v in VOTERS)
        expected = votes / 4 * 100 if row["overall_signal"] != "HOLD" else 0
        assert row["signal_strength"] == expected


def test_signals_never_look_ahead():
    prices = synthetic_prices(days=400)
    full, _ = TechnicalIndicators.generate_signals(prices)
    cutoff = 250
    truncated, _ = TechnicalIndicators.generate_signals(prices.iloc[:cutoff])
    cols = VOTERS + ["overall_signal", "signal_strength"]
    assert full.iloc[:cutoff][cols].equals(truncated[cols])


def test_exits_respect_stop_loss_and_take_profit():
    strategy = TradingStrategy(position_size=0.95, stop_loss=0.03, take_profit=0.20)
    trades, _, _ = strategy.execute_backtest(synthetic_prices(seed=11))
    assert len(trades) > 0
    stops = trades[trades["exit_reason"] == "STOP_LOSS"]
    targets = trades[trades["exit_reason"] == "TAKE_PROFIT"]
    assert (stops["profit_loss_pct"] <= -3 + 1e-9).all()
    assert (targets["profit_loss_pct"] >= 20 - 1e-9).all()


def test_evaluator_reproduces_original_backtester_exactly():
    for seed, (pos, sl, tp) in itertools.product(
        [3, 7, 11], [(0.95, 0.03, 0.20), (1.0, 0.10, 0.10), (0.9, 0.05, 0.25)]
    ):
        prices = synthetic_prices(seed=seed)
        original_trades, _, original = TradingStrategy(
            position_size=pos, stop_loss=sl, take_profit=tp
        ).execute_backtest(prices)

        signals, _ = TechnicalIndicators.generate_signals(prices)
        equity, trades, final = simulate(signals, pos, sl, tp, cost=0.0)
        mine = strategy_metrics(equity, trades, final)

        assert len(trades) == len(original_trades)
        for col in ["entry_date", "exit_date", "exit_reason"]:
            assert list(trades[col]) == list(original_trades[col])
        for col in ["entry_price", "exit_price", "profit_loss"]:
            assert np.allclose(trades[col], original_trades[col])
        assert math.isclose(mine["return_pct"], original["total_return_pct"], rel_tol=1e-9, abs_tol=1e-9)
        assert math.isclose(mine["sharpe"], original["sharpe_ratio"], rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(mine["max_drawdown_pct"], original["max_drawdown"], rel_tol=1e-9, abs_tol=1e-9)


def test_costs_only_ever_reduce_the_return():
    signals, _ = TechnicalIndicators.generate_signals(synthetic_prices(seed=3))
    returns = [
        strategy_metrics(*simulate(signals, 0.95, 0.03, 0.20, cost=c))["return_pct"]
        for c in (0.0, 0.001, 0.005)
    ]
    assert returns[0] > returns[1] > returns[2]


def test_buy_and_hold_return():
    result = buy_and_hold_metrics([100.0, 120.0, 90.0, 150.0])
    assert math.isclose(result["return_pct"], 50.0)
    assert math.isclose(result["max_drawdown_pct"], -25.0)
