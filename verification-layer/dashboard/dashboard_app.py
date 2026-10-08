"""
dashboard_app.py

Flask backend for the ChainProof dashboard.

The server's only job is to hand the browser the *published* data: the 30
decisions from results/chainproof_replay_decisions.csv, each with the exact
canonical JSON that verify.py hashes. The browser then does the checking on
its own: it hashes that JSON with keccak256, reads the commitment from the
ChainProofRegistry contract on Sepolia directly, and recovers the signer.
So a visitor doesn't have to trust this server. If it served altered data,
the hashes would stop matching what is on-chain.

Run from verification-layer/:
    python dashboard/dashboard_app.py
Then open http://localhost:5002
"""

import csv
import json
import os
import sys

import pandas as pd
from flask import Flask, jsonify, render_template

HERE = os.path.dirname(os.path.abspath(__file__))
LAYER_DIR = os.path.join(HERE, "..")
sys.path.append(LAYER_DIR)

from verify import (  # noqa: E402
    CONTRACT_ADDRESS,
    DECISIONS_CSV,
    EXPECTED_ATTESTER,
    RISK_PARAMS,
    canonical_payload,
)

RESULTS_DIR = os.path.join(LAYER_DIR, "results")
REPO_URL = "https://github.com/Zenish2001/ChainProof"

# Read-only RPC endpoints the browser may use. BROWSER_RPC_URL, if set, is
# tried first. Anything put here is visible to visitors, so only use a key
# that is restricted to this site's domain.
PUBLIC_RPCS = [
    "https://ethereum-sepolia-rpc.publicnode.com",
    "https://sepolia.drpc.org",
    "https://1rpc.io/sepolia",
]

ERC8004 = {
    "agent_id": 9896,
    "identity_registry": "0x8004A818BFB912233c491871b3d84c89A494BD9e",
    "validation_registry": "0xC640b92bAe5C832c8C8787F4F0fB894EF3De0d77",
    "validator": "0xf3eF4e50A01d6ec110A231BF2C57E6aE8E625856",
    "registration_tx": "0xb5c10780c1e8a9cfd31fffa537c763614995dd5346ad18fc3c4629394f6ea615",
    "request_tx": "0x66f3b6544d768c25a0cd9baf98bfec13e3f8556bdce18368ccf1865d34c6e64d",
    "verdict_tx": "0x4cc7b8e25495112ed845fa82dc7215394e38ebeb4f7a887188f438cf5739504f",
    "agent_card": "https://raw.githubusercontent.com/Zenish2001/ChainProof/main/agent.json",
}

app = Flask(__name__)


def _clean(value):
    """NaN can't be sent as JSON; send None instead (display only)."""
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def build_data():
    df = pd.read_csv(DECISIONS_CSV)

    onchain_log = {}
    log_path = os.path.join(RESULTS_DIR, "chainproof_onchain_log.csv")
    if os.path.exists(log_path):
        with open(log_path) as f:
            for row in csv.DictReader(f):
                onchain_log[int(row["onchain_index"])] = row

    decisions = []
    for i in range(len(df)):
        payload = canonical_payload(df.iloc[i])
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        log = onchain_log.get(i, {})
        decisions.append({
            "index": i,
            "payload": _clean(payload),
            # The exact string verify.py hashes. The browser hashes this
            # string itself; nothing here is a precomputed hash.
            "canonical": canonical,
            "tx_hash": log.get("tx_hash"),
            "block_number": int(log["block_number"]) if log.get("block_number") else None,
        })

    performance = []
    comparison_path = os.path.join(RESULTS_DIR, "strategy_comparison.csv")
    if os.path.exists(comparison_path):
        with open(comparison_path) as f:
            for row in csv.DictReader(f):
                performance.append({
                    "symbol": row["symbol"],
                    "return_pct": float(row["best_return"]),
                    "win_rate_pct": float(row["win_rate"]),
                    "sharpe": float(row["sharpe_ratio"]),
                    "stop_loss": float(row["stop_loss"]),
                    "take_profit": float(row["take_profit"]),
                    "position_size": float(row["position_size"]),
                })

    rpcs = [os.environ.get("BROWSER_RPC_URL")] + PUBLIC_RPCS
    return {
        "chain_id": 11155111,
        "contract": CONTRACT_ADDRESS,
        "attester": EXPECTED_ATTESTER,
        "risk_params": RISK_PARAMS,
        "rpc_urls": [u for u in rpcs if u],
        "decisions": decisions,
        "performance": performance,
        "erc8004": ERC8004,
        "repo_url": REPO_URL,
    }


DATA = build_data()


@app.route("/")
def dashboard():
    return render_template("chainproof_dashboard.html", repo_url=REPO_URL, contract=CONTRACT_ADDRESS)


@app.route("/api/data")
def data():
    resp = jsonify(DATA)
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.route("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    print("ChainProof dashboard at http://localhost:5002")
    app.run(debug=True, port=5002, use_reloader=False)
