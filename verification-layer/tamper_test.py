#!/usr/bin/env python3
"""
tamper_test.py -- shows the verifier catches tampering

Reuses verify.py's own functions (not a reimplementation) to run three
cases against the live Sepolia record for one decision:

  1. The genuine, untampered decision        -> hash matches on-chain
  2. The same decision with the price +$500  -> hash does NOT match
  3. The same decision with one indicator
     signal flipped (e.g. BUY -> SELL)       -> hash does NOT match

The point is that the verifier rejects anything that differs from what was
committed, rather than rubber-stamping any row shaped like a valid decision.

Run from verification-layer/:
    pip install -r requirements.txt
    python tamper_test.py            # tests decision #0
    python tamper_test.py 7          # tests decision #7
"""

import sys

import pandas as pd

from verify import DECISIONS_CSV, check_decision, connect

FLIP = {"BUY": "SELL", "SELL": "BUY", "HOLD": "BUY"}


def run_case(label, row, onchain, expect_hash_ok):
    hash_ok, signer_ok, recomputed = check_decision(row, onchain)
    passed = hash_ok == expect_hash_ok
    verdict = "matches on-chain" if hash_ok else "DOES NOT match on-chain"
    print(f"  {label:<34} {recomputed[:16]}...  {verdict}   "
          f"[{'as expected' if passed else 'UNEXPECTED'}]")
    return passed


def main():
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    df = pd.read_csv(DECISIONS_CSV)
    if not 0 <= index < len(df):
        sys.exit(f"Decision index must be between 0 and {len(df) - 1}")

    contract = connect()
    onchain = contract.functions.getCommitment(index).call()
    genuine = df.iloc[index]

    print("=" * 72)
    print(f"CHAINPROOF -- TAMPER TEST ON DECISION #{index}")
    print(f"  {genuine['action']} at {genuine['timestamp']}, price {genuine['price']}")
    print("=" * 72)

    price_tampered = genuine.copy()
    price_tampered["price"] = float(genuine["price"]) + 500

    signal_tampered = genuine.copy()
    ind_cols = sorted(c for c in genuine.index if c.startswith("ind_"))
    col = ind_cols[0]
    signal_tampered[col] = FLIP.get(str(genuine[col]), "BUY")

    results = [
        run_case("1. genuine", genuine, onchain, expect_hash_ok=True),
        run_case("2. price + $500", price_tampered, onchain, expect_hash_ok=False),
        run_case(f"3. {col}: {genuine[col]} -> {signal_tampered[col]}",
                 signal_tampered, onchain, expect_hash_ok=False),
    ]

    print("=" * 72)
    if all(results):
        print("PASS: genuine decision verified; both tampered versions rejected.")
    else:
        print("FAIL: the verifier did not behave as expected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
