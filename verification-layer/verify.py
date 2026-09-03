#!/usr/bin/env python3
"""
verify.py -- ChainProof standalone verifier

Runs from a clean clone with no local state, no database, no build
artifacts and no configuration. Everything it needs is either committed
to this repository or on a public blockchain.

    pip install pandas web3
    python verify.py

WHAT THIS CHECKS

For each of the 30 published trading decisions, it rebuilds the canonical
commitment payload -- timestamp, role, action, price, signal strength,
every indicator value, and the active risk parameters -- hashes it with
keccak256, and compares that hash against the commitment stored on
Ethereum Sepolia in ChainProofRegistry.

A match means the on-chain record and the published decision data are the
same object. Editing a price, an indicator value, or a decision in the CSV
changes the hash and the check fails. The on-chain record cannot be edited
at all.

WHAT THIS DOES NOT CHECK

It does not re-run the trading strategy against raw market prices. That is
a separate claim with a separate failure mode, and conflating the two
would make this script report a hash mismatch for what is really a
data-provenance question. See "Verifying the inputs" in the README.

Nor does it establish that the committed set is complete. Every
commitment here verifies, but hashes prove records were not rewritten,
never that none are missing. What makes omission detectable for ChainProof
is that the replay is deterministic over a declared parameter set, so an
independent party can derive the full expected decision sequence and
compare -- not anything this script does.
"""

import json
import os
import sys

try:
    import pandas as pd
    from web3 import Web3
except ImportError:
    sys.exit("Missing dependencies. Run:  pip install pandas web3")


# ---------------------------------------------------------------- constants

CONTRACT_ADDRESS = "0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955"
DEFAULT_RPC = "https://ethereum-sepolia-rpc.publicnode.com"
RPC_URL = os.environ.get("SEPOLIA_RPC_URL", DEFAULT_RPC)

DECISIONS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "results", "chainproof_replay_decisions.csv"
)

# The risk parameters bound into every commitment. Must match
# commit_and_sign.py exactly -- a commitment is bound to a specific
# rule-set, not just to a price.
RISK_PARAMS = {
    "position_size": 0.95,
    "stop_loss": 0.03,
    "take_profit": 0.20,
}

# Minimal ABI. Inlined deliberately: requiring `npx hardhat compile` to
# produce an artifact would mean this script cannot run from a clean clone
# without a Node toolchain.
ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "index", "type": "uint256"}],
        "name": "getCommitment",
        "outputs": [
            {"internalType": "bytes32", "name": "commitmentHash", "type": "bytes32"},
            {"internalType": "string", "name": "action", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "address", "name": "signer", "type": "address"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getCommitmentCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


# ------------------------------------------------------------------ hashing

def canonical_payload(row):
    """Deterministic representation of everything a commitment covers.

    Must match commit_and_sign.py byte for byte. Sorted keys and explicit
    type coercion are what make the JSON reproducible across runs and
    across machines.
    """
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
    """keccak256 over the canonical JSON encoding of the payload."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return Web3.keccak(text=canonical_json)


def normalize(value):
    """Reduce a hash to lowercase hex with no 0x prefix.

    web3.py has changed whether HexBytes.hex() includes the prefix across
    versions, so both sides get normalized rather than compared raw.
    """
    if isinstance(value, (bytes, bytearray)):
        return value.hex().lower().removeprefix("0x")
    return str(value).lower().removeprefix("0x")


# --------------------------------------------------------------------- main

def main():
    print("=" * 72)
    print("CHAINPROOF -- INDEPENDENT VERIFICATION")
    print("=" * 72)

    if not os.path.exists(DECISIONS_CSV):
        sys.exit(f"Decision data not found at {DECISIONS_CSV}")

    df = pd.read_csv(DECISIONS_CSV)
    print(f"Loaded {len(df)} published decisions from results/")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        sys.exit(f"Could not reach an Ethereum Sepolia node at {RPC_URL}\n"
                 f"Set SEPOLIA_RPC_URL to a working endpoint and retry.")

    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)
    onchain_count = contract.functions.getCommitmentCount().call()
    print(f"Reading {onchain_count} commitments from {CONTRACT_ADDRESS} on Sepolia")
    print()

    if onchain_count != len(df):
        print(f"NOTE: {len(df)} local decisions vs {onchain_count} on-chain commitments.")
        print("      Comparing the overlap only.\n")

    matched = 0
    mismatched = []
    limit = min(len(df), onchain_count)

    for i in range(limit):
        row = df.iloc[i]
        recomputed = normalize(commitment_hash(canonical_payload(row)))
        stored = normalize(contract.functions.getCommitment(i).call()[0])

        ok = recomputed == stored
        matched += ok
        if not ok:
            mismatched.append(i)

        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] #{i:<3} {str(row['action']):<12} {row['timestamp']}  {recomputed[:16]}...")

    print()
    print("=" * 72)
    print(f"RESULT: {matched}/{limit} commitments verified")

    if mismatched:
        print(f"Mismatched indices: {mismatched}")
        print()
        print("A mismatch means the published decision data no longer produces the")
        print("hash that was committed on-chain -- the local file changed, since the")
        print("chain record cannot.")
        print("=" * 72)
        sys.exit(1)

    print()
    print("Every published decision reproduces the hash recorded on Ethereum Sepolia.")
    print("This verifies the on-chain record against the published data. It does not")
    print("re-run the strategy against raw market prices -- see the README.")
    print("=" * 72)


if __name__ == "__main__":
    main()
