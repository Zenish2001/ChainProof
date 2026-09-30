#!/usr/bin/env python3
"""
replay_check.py -- re-runs the strategy from raw prices

verify.py shows the published decisions match the chain. This closes the
other half: it re-runs the unmodified strategy over the committed price
fixture (fixtures/BTC-USD.csv), rebuilds the 30 decisions with the same
function that produced them (generate_replay_data.build_decisions), and
checks that each one hashes to the commitment that was published.

    pip install -r requirements.txt
    python replay_check.py

Together with verify.py, a pass means: the committed hashes on Sepolia are
exactly what the declared strategy produces from these prices. No database,
no keys and no network are needed for this step.
"""

import io
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "trading-bot"))

from generate_replay_data import SYMBOL, build_decisions  # noqa: E402
from price_data import load_prices_csv  # noqa: E402
from verify import canonical_payload, commitment_hash, normalize  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", f"{SYMBOL}.csv")
COMMITMENTS_CSV = os.path.join(HERE, "results", "chainproof_commitments.csv")


def main():
    print("=" * 72)
    print("CHAINPROOF -- REPLAY FROM RAW PRICES")
    print("=" * 72)

    if not os.path.exists(FIXTURE):
        sys.exit(f"No price fixture at {os.path.relpath(FIXTURE, HERE)}. "
                 "Run export_price_fixture.py on the machine with the database.")

    prices = load_prices_csv(FIXTURE)
    print(f"Loaded {len(prices)} {SYMBOL} prices, {prices.index[0].date()} to {prices.index[-1].date()}")

    decisions, performance = build_decisions(prices)
    print(f"Backtest: {performance['total_trades']} closed trades, "
          f"{performance['total_return_pct']:.2f}% return, Sharpe {performance['sharpe_ratio']:.2f}")

    # Round-trip through CSV exactly as the original pipeline did
    # (generate_replay_data.py wrote a CSV, commit_and_sign.py read it), so
    # every value is hashed in the same representation.
    buffer = io.StringIO()
    decisions.to_csv(buffer, index=False)
    buffer.seek(0)
    decisions = pd.read_csv(buffer)

    committed = pd.read_csv(COMMITMENTS_CSV)
    print(f"Comparing against {len(committed)} published commitments\n")

    if len(decisions) != len(committed):
        print(f"NOTE: replay produced {len(decisions)} decisions, {len(committed)} were committed.\n")

    matched = 0
    for i in range(min(len(decisions), len(committed))):
        row = decisions.iloc[i]
        recomputed = normalize(commitment_hash(canonical_payload(row)))
        ok = recomputed == normalize(committed.iloc[i]["commitment_hash"])
        matched += ok
        print(f"  [{'OK  ' if ok else 'FAIL'}] #{i:<3} {str(row['action']):<12} {row['timestamp']}  {recomputed[:16]}...")

    total = len(committed)
    print()
    print("=" * 72)
    print(f"RESULT: {matched}/{total} committed decisions reproduced from raw prices")
    print("=" * 72)
    if matched != total:
        print("A failure here means the fixture is not the price data the original run")
        print("used, or the strategy code has changed since the commitments were made.")
        sys.exit(1)


if __name__ == "__main__":
    main()
