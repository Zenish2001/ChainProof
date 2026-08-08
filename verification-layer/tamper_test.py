"""
tamper_test.py

The proposal's final success criterion: "one deliberately tampered trade
that the verifier correctly flags."

This reuses verifier.py's own functions directly (not a reimplementation)
to show two things side by side:

  1. A genuine, untampered decision -- recomputed hash matches on-chain.
  2. The SAME decision, with one input deliberately altered (price bumped
     by $500) -- recomputed hash does NOT match on-chain, proving the
     verifier catches tampering rather than rubber-stamping anything
     that's shaped like a valid commitment.

Run from the project root:
    python chainproof/tamper_test.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from verifier import (
    regenerate_decisions_independently,
    canonical_payload,
    commitment_hash,
    fetch_onchain_commitments,
)

TAMPER_INDEX = 0          # which decision (0-29) to test
TAMPER_PRICE_DELTA = 500  # dollars added to the price to simulate tampering


def main():
    print("=" * 70)
    print("CHAINPROOF -- TAMPER-DETECTION TEST")
    print("=" * 70)

    print("\nRe-running strategy code and fetching on-chain commitments...")
    decisions_df = regenerate_decisions_independently()
    onchain = fetch_onchain_commitments()

    row = decisions_df.iloc[TAMPER_INDEX]
    onchain_entry = onchain[TAMPER_INDEX]
    onchain_hash = onchain_entry["commitment_hash"]

    # ---- 1. Genuine check ----------------------------------------------
    genuine_hash = commitment_hash(canonical_payload(row))
    genuine_ok = genuine_hash == onchain_hash

    print("\n" + "-" * 70)
    print(f"TEST 1 -- Genuine decision #{TAMPER_INDEX}")
    print("-" * 70)
    print(f"  Action:      {row['action']}")
    print(f"  Price:       ${row['price']:.2f}")
    print(f"  Recomputed:  {genuine_hash}")
    print(f"  On-chain:    {onchain_hash}")
    print(f"  Result:      {'MATCH -- as expected' if genuine_ok else 'MISMATCH -- unexpected!'}")

    # ---- 2. Tampered check ----------------------------------------------
    tampered_row = row.copy()
    tampered_row["price"] = tampered_row["price"] + TAMPER_PRICE_DELTA
    tampered_hash = commitment_hash(canonical_payload(tampered_row))
    tampered_caught = tampered_hash != onchain_hash

    print("\n" + "-" * 70)
    print(f"TEST 2 -- Same decision, price tampered by +${TAMPER_PRICE_DELTA}")
    print("-" * 70)
    print(f"  Claimed price:        ${row['price']:.2f}")
    print(f"  Tampered price:       ${tampered_row['price']:.2f}")
    print(f"  Recomputed (tampered): {tampered_hash}")
    print(f"  On-chain (real):       {onchain_hash}")
    print(f"  Result:      {'MISMATCH -- tampering correctly detected!' if tampered_caught else 'MATCH -- BAD, tamper was NOT detected!'}")

    print("\n" + "=" * 70)
    if genuine_ok and tampered_caught:
        print("SUCCESS: genuine data verifies correctly, and tampering is caught.")
    else:
        print("FAILURE: something is wrong with the verification logic -- investigate.")
    print("=" * 70)


if __name__ == "__main__":
    main()