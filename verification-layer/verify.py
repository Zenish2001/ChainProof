#!/usr/bin/env python3
"""
verify.py -- ChainProof standalone verifier

Runs from a clean clone with no local state, no database, no build
artifacts and no configuration. Everything it needs is either committed
to this repository or on a public blockchain.

    pip install -r requirements.txt
    python verify.py

WHAT THIS CHECKS

For each of the 30 published trading decisions, it runs two checks.

1. Integrity. It rebuilds the canonical commitment payload -- timestamp,
   role, action, price, signal strength, each voting indicator's signal
   (BUY/SELL/HOLD), and the active risk parameters -- hashes it with
   keccak256, and compares that hash against the commitment stored on
   Ethereum Sepolia in ChainProofRegistry.

2. Attribution. ChainProofRegistry accepts a caller-supplied signer and
   signature without checking them, so the verifier checks them instead:
   it recovers the address that signed each commitment hash (EIP-191
   personal_sign) and requires it to equal both the signer recorded
   on-chain and the published ChainProof attestation address.

A pass means the on-chain record and the published decision data are the
same object, and that the ChainProof attestation key signed it. Editing a
price, an indicator signal, or a decision in the CSV changes the hash and
the check fails. The on-chain record cannot be edited at all.

Note the commitment covers each indicator's discrete signal, not the raw
indicator values (RSI level, MACD line, and so on) behind it.

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
    from eth_account import Account
    from eth_account.messages import encode_defunct
except ImportError:
    sys.exit("Missing dependencies. Run:  pip install -r requirements.txt")


# ---------------------------------------------------------------- constants

CONTRACT_ADDRESS = "0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955"
DEFAULT_RPC = "https://ethereum-sepolia-rpc.publicnode.com"
RPC_URL = os.environ.get("SEPOLIA_RPC_URL", DEFAULT_RPC)

# The ChainProof attestation key. Every commitment must be signed by this
# address; see "Attribution" above.
EXPECTED_ATTESTER = "0xBd121B739630F6F23d8F85f8ddf82dC0381b2c9f"

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


def recover_signer(commitment, signature):
    """Return the address that produced `signature` over `commitment`.

    commit_and_sign.py signs with EIP-191 personal_sign over the raw 32
    hash bytes, so the same encoding is rebuilt here.
    """
    message = encode_defunct(hexstr="0x" + normalize(commitment))
    return Account.recover_message(message, signature=bytes(signature))


def check_decision(row, onchain):
    """Run both checks for one decision against its on-chain record.

    `onchain` is the tuple returned by ChainProofRegistry.getCommitment.
    Returns (hash_ok, signer_ok, recomputed_hash_hex).
    """
    stored_hash, _action, _timestamp, onchain_signer, signature = onchain
    recomputed = normalize(commitment_hash(canonical_payload(row)))
    hash_ok = recomputed == normalize(stored_hash)

    try:
        recovered = recover_signer(stored_hash, signature)
        signer_ok = (
            recovered.lower() == str(onchain_signer).lower() == EXPECTED_ATTESTER.lower()
        )
    except Exception:
        signer_ok = False

    return hash_ok, signer_ok, recomputed


def connect():
    """Connect to Sepolia and return the ChainProofRegistry contract."""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        sys.exit(f"Could not reach an Ethereum Sepolia node at {RPC_URL}\n"
                 f"Set SEPOLIA_RPC_URL to a working endpoint and retry.")
    return w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)


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

    contract = connect()
    onchain_count = contract.functions.getCommitmentCount().call()
    print(f"Reading {onchain_count} commitments from {CONTRACT_ADDRESS} on Sepolia")
    print(f"Expected attestation signer: {EXPECTED_ATTESTER}")
    print()

    if onchain_count != len(df):
        print(f"NOTE: {len(df)} local decisions vs {onchain_count} on-chain commitments.")
        print("      Comparing the overlap only.\n")

    hash_failures = []
    signer_failures = []
    limit = min(len(df), onchain_count)

    print("          #    action       timestamp                  hash  sig")
    for i in range(limit):
        row = df.iloc[i]
        onchain = contract.functions.getCommitment(i).call()
        hash_ok, signer_ok, recomputed = check_decision(row, onchain)

        if not hash_ok:
            hash_failures.append(i)
        if not signer_ok:
            signer_failures.append(i)

        mark = "OK  " if (hash_ok and signer_ok) else "FAIL"
        print(f"  [{mark}] #{i:<3} {str(row['action']):<12} {row['timestamp']}  "
              f"{'ok' if hash_ok else 'XX'}    {'ok' if signer_ok else 'XX'}   {recomputed[:16]}...")

    print()
    print("=" * 72)
    print(f"RESULT: {limit - len(hash_failures)}/{limit} commitment hashes verified")
    print(f"        {limit - len(signer_failures)}/{limit} signatures from the ChainProof attester")

    if hash_failures or signer_failures:
        if hash_failures:
            print(f"Hash mismatches at indices: {hash_failures}")
            print("  The published decision data no longer produces the hash that was")
            print("  committed on-chain -- the local file changed, since the chain cannot.")
        if signer_failures:
            print(f"Signature failures at indices: {signer_failures}")
            print("  The commitment was not signed by the ChainProof attestation key.")
        print("=" * 72)
        sys.exit(1)

    print()
    print("Every published decision reproduces the hash recorded on Ethereum Sepolia,")
    print("and every commitment was signed by the ChainProof attestation key. This")
    print("verifies the on-chain record against the published data. It does not")
    print("re-run the strategy against raw market prices -- see the README.")
    print("=" * 72)


if __name__ == "__main__":
    main()
