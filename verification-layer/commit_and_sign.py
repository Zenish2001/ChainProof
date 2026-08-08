"""
commit_and_sign.py

Turns each replayed trading decision into a single on-chain-ready
commitment:

  1. Builds a canonical (deterministic) representation of everything the
     proposal says should be committed: the inputs (price + every
     indicator value), the timestamp, the decision (BUY/SELL/etc.), and
     the risk-rule parameters active for this run (position_size,
     stop_loss, take_profit) -- so a commitment is bound to a specific
     rule-set, not just a bare price.
  2. Hashes that canonical representation with keccak256 (Ethereum's
     native hash), matching what the Solidity contract and the later
     verifier will both work with.
  3. Signs each commitment hash with a local private key -- this is the
     proposal's explicitly-scoped attestation simplification, standing in
     for real TEE remote attestation.

Output: data/chainproof_commitments.csv, with one row per decision,
columns = original decision data + commitment_hash + signer_address +
signature. This file is what the next script submits on-chain.

Run from the project root:
    pip install web3 eth-account --break-system-packages   # if not installed
    python chainproof/commit_and_sign.py
"""

import json
import os
import pandas as pd
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

INPUT_PATH = "data/chainproof_replay_decisions.csv"
OUTPUT_PATH = "data/chainproof_commitments.csv"
KEY_PATH = "chainproof/attestation_key.json"

# The risk-rule parameters active for the backtest run being verified.
# These come from strategy_comparison.csv's winning BTC-USD row and are
# bound into every commitment, since the proposal treats "declared
# strategy" as signal logic + these specific risk rules together.
RISK_PARAMS = {
    "position_size": 0.95,
    "stop_loss": 0.03,
    "take_profit": 0.20,
}


def get_or_create_attestation_key():
    """Load a persistent local signing key, or create one on first run.

    This is the proposal's stated simplification: a dedicated local key
    signs each commitment, standing in for real TEE-based remote
    attestation. Persisting it means every run signs with the same
    identity instead of a fresh throwaway key each time.
    """
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH) as f:
            data = json.load(f)
        return Account.from_key(data["private_key"])

    account = Account.create()
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    with open(KEY_PATH, "w") as f:
        json.dump({
            "address": account.address,
            "private_key": account.key.hex(),
        }, f, indent=2)
    print(f"Created new attestation key: {account.address}")
    print(f"Saved to {KEY_PATH} (local-only, mocked attestation -- not a production secret)")
    return account


def canonical_payload(row):
    """Build a deterministic dict of everything this commitment covers:
    the input snapshot (price + every indicator column) plus the decision
    plus the risk parameters. Sorted keys + explicit str conversion keeps
    this reproducible across runs and across the later verifier script."""
    payload = {
        "timestamp": str(row["timestamp"]),
        "role": row["role"],
        "action": row["action"],
        "price": float(row["price"]),
        "signal_strength": float(row["signal_strength"]) if pd.notna(row["signal_strength"]) else None,
        "overall_signal": row.get("overall_signal"),
        "risk_params": RISK_PARAMS,
    }

    indicator_cols = sorted([c for c in row.index if c.startswith("ind_")])
    payload["indicators"] = {
        col: (float(row[col]) if pd.notna(row[col]) and isinstance(row[col], (int, float)) else str(row[col]))
        for col in indicator_cols
    }

    return payload


def commitment_hash(payload):
    """keccak256 of the canonical JSON representation of the payload."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return Web3.keccak(text=canonical_json).hex()


def main():
    print("=" * 70)
    print("CHAINPROOF -- COMPUTING COMMITMENTS AND SIGNING")
    print("=" * 70)

    if not os.path.exists(INPUT_PATH):
        print(f"{INPUT_PATH} not found. Run generate_replay_data.py first.")
        return

    df = pd.read_csv(INPUT_PATH)
    print(f"Loaded {len(df)} replayed decisions from {INPUT_PATH}")

    account = get_or_create_attestation_key()
    print(f"Signing with attestation key: {account.address}")

    records = []
    for _, row in df.iterrows():
        payload = canonical_payload(row)
        c_hash = commitment_hash(payload)

        message = encode_defunct(hexstr=c_hash)
        signed = account.sign_message(message)

        records.append({
            "timestamp": row["timestamp"],
            "role": row["role"],
            "action": row["action"],
            "price": row["price"],
            "signal_strength": row["signal_strength"],
            "commitment_hash": c_hash,
            "signer_address": account.address,
            "signature": signed.signature.hex(),
        })

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nComputed {len(out_df)} commitments")
    print("\nPreview:")
    print(out_df[["timestamp", "action", "price", "commitment_hash"]].head(5).to_string())
    print(f"\nSaved to: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
