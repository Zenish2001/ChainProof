"""
verifier.py

The independent verifier. Per the proposal: "an independent script pulls
the same price_history data, independently re-imports and re-runs
technical_indicators.py and trading_strategy.py exactly as they exist in
my repository, recomputes the commitment, and checks it against what was
published on-chain."

Critically, this script does NOT read chainproof_replay_decisions.csv or
chainproof_commitments.csv -- those were produced by earlier steps, and
trusting them here would defeat the purpose. Instead it:

  1. Re-fetches the same price data from trading_bot.db
  2. Re-runs the unmodified TechnicalIndicators.generate_signals() and
     TradingStrategy.execute_backtest() from scratch
  3. Rebuilds the same decision events and canonical payloads
  4. Recomputes each commitment hash independently
  5. Pulls the actual on-chain commitments directly from the deployed
     contract (not from any local log file)
  6. Compares recomputed hash vs. on-chain hash, one by one

Requires: chainproof/artifacts/contracts/ChainProofRegistry.sol/ChainProofRegistry.json
(created automatically by `npx hardhat compile`)

Run from the project root:
    python chainproof/verifier.py
"""

import json
import os
import sys

import pandas as pd
from web3 import Web3

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from data.database import TradingDatabase
from indicators.technical_indicators import TechnicalIndicators
from strategies.trading_strategy import TradingStrategy

# ============================================================
# Must match generate_replay_data.py / commit_and_sign.py exactly,
# and your deployed contract address.
# ============================================================
SYMBOL = "BTC-USD"
POSITION_SIZE = 0.95
STOP_LOSS = 0.03
TAKE_PROFIT = 0.20
MAX_DECISIONS = 30

CONTRACT_ADDRESS = "0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955"
SEPOLIA_RPC_URL = os.environ.get("SEPOLIA_RPC_URL") or None  # falls back to reading .env below

RISK_PARAMS = {
    "position_size": POSITION_SIZE,
    "stop_loss": STOP_LOSS,
    "take_profit": TAKE_PROFIT,
}

ARTIFACT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "artifacts", "contracts", "ChainProofRegistry.sol", "ChainProofRegistry.json"
)


def load_env_rpc_url():
    """Minimal .env reader, so this script doesn't require python-dotenv."""
    global SEPOLIA_RPC_URL
    if SEPOLIA_RPC_URL:
        return
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("SEPOLIA_RPC_URL="):
                    SEPOLIA_RPC_URL = line.strip().split("=", 1)[1]
                    return


def regenerate_decisions_independently():
    """Steps 1-3: re-fetch data and re-run the unmodified strategy code
    from scratch. This mirrors generate_replay_data.py exactly, but is
    kept as its own separate function here so the verifier never has to
    trust that earlier script's cached output."""
    db = TradingDatabase()
    df = db.get_price_data(SYMBOL)

    signals, _ = TechnicalIndicators.generate_signals(df)

    strategy = TradingStrategy(
        initial_capital=10000,
        position_size=POSITION_SIZE,
        stop_loss=STOP_LOSS,
        take_profit=TAKE_PROFIT,
    )
    trades_df, _, performance = strategy.execute_backtest(df, SYMBOL)

    print(f"Independently re-ran backtest: {performance['total_trades']} trades, "
          f"{performance['total_return_pct']:.2f}% return, "
          f"Sharpe {performance['sharpe_ratio']:.2f}")

    decisions = []
    for _, trade in trades_df.iterrows():
        for role, date_col, price_col, action in [
            ("ENTRY", "entry_date", "entry_price", "BUY"),
            ("EXIT", "exit_date", "exit_price", "SELL"),
        ]:
            ts = trade[date_col]
            if ts not in signals.index:
                continue
            snapshot = signals.loc[ts]

            decision = {
                "timestamp": ts,
                "role": role,
                "action": action if role == "ENTRY" else trade["exit_reason"],
                "price": trade[price_col],
                "signal_strength": snapshot.get("signal_strength"),
                "overall_signal": snapshot.get("overall_signal"),
            }
            for col in signals.columns:
                if col not in ("price", "signal_strength", "overall_signal"):
                    decision[f"ind_{col}"] = snapshot.get(col)
            decisions.append(decision)

    decisions_df = pd.DataFrame(decisions).sort_values("timestamp").reset_index(drop=True)
    return decisions_df.head(MAX_DECISIONS)


def canonical_payload(row):
    """Must exactly match commit_and_sign.py's canonical_payload()."""
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
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return Web3.keccak(text=canonical_json).hex()


def fetch_onchain_commitments():
    """Step 5: pull commitments directly from the live contract -- not
    from any local CSV log."""
    load_env_rpc_url()
    if not SEPOLIA_RPC_URL:
        raise RuntimeError("SEPOLIA_RPC_URL not found in environment or .env")
    if CONTRACT_ADDRESS == "PASTE_YOUR_CONTRACT_ADDRESS_HERE":
        raise RuntimeError("Set CONTRACT_ADDRESS at the top of this script.")

    with open(ARTIFACT_PATH) as f:
        artifact = json.load(f)
    abi = artifact["abi"]

    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

    count = contract.functions.getCommitmentCount().call()
    print(f"Contract reports {count} commitments on-chain")

    onchain = []
    for i in range(count):
        commitment_hash_, action, timestamp, signer, signature = contract.functions.getCommitment(i).call()
        onchain.append({
            "index": i,
            "commitment_hash": commitment_hash_.hex(),
            "action": action,
            "timestamp": timestamp,
            "signer": signer,
        })
    return onchain


def main():
    print("=" * 70)
    print("CHAINPROOF -- INDEPENDENT VERIFIER")
    print("=" * 70)
    print("\nStep 1-3: Re-running strategy code from scratch (not trusting cached CSVs)...")
    decisions_df = regenerate_decisions_independently()
    print(f"Regenerated {len(decisions_df)} decisions independently\n")

    print("Step 4: Recomputing commitment hashes...")
    recomputed = [commitment_hash(canonical_payload(row)) for _, row in decisions_df.iterrows()]
    print(f"Recomputed {len(recomputed)} hashes\n")

    print("Step 5: Fetching commitments directly from the live contract...")
    onchain = fetch_onchain_commitments()
    print()

    print("Step 6: Comparing recomputed hashes against on-chain records...\n")
    print(f"{'#':<4}{'Action':<12}{'On-chain hash (prefix)':<26}{'Recomputed (prefix)':<26}{'Result'}")
    print("-" * 80)

    matches, mismatches = 0, 0
    for i, entry in enumerate(onchain):
        onchain_h = entry["commitment_hash"]
        recomputed_h = recomputed[i] if i < len(recomputed) else None
        ok = (recomputed_h is not None) and (onchain_h == recomputed_h)

        print(f"{i:<4}{entry['action']:<12}{onchain_h[:20]+'...':<26}"
              f"{(recomputed_h[:20]+'...' if recomputed_h else 'N/A'):<26}"
              f"{'MATCH' if ok else 'MISMATCH !!'}")

        matches += ok
        mismatches += not ok

    print("\n" + "=" * 70)
    print(f"RESULT: {matches}/{len(onchain)} commitments verified successfully")
    if mismatches:
        print(f"WARNING: {mismatches} commitment(s) did NOT match -- tampering or corruption detected.")
    else:
        print("All on-chain commitments match independently recomputed values.")
    print("=" * 70)


if __name__ == "__main__":
    main()