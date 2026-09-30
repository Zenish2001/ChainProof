"""
dashboard_app.py

Flask backend for the ChainProof results dashboard. It reuses verify.py's
own functions directly, so "Run Verification" and "Run Tamper Test" on the
dashboard run exactly the same checks as `python verify.py` and
`python tamper_test.py` in the terminal: recompute each commitment hash
from results/chainproof_replay_decisions.csv, read the live contract on
Sepolia, compare, and check each signature.

Run from verification-layer/:
    python dashboard/dashboard_app.py
Then open http://localhost:5002
"""

import csv
import os
import sys

import pandas as pd
from flask import Flask, jsonify, render_template

HERE = os.path.dirname(os.path.abspath(__file__))
LAYER_DIR = os.path.join(HERE, "..")
sys.path.append(LAYER_DIR)

app = Flask(__name__)

from verify import (  # noqa: E402
    CONTRACT_ADDRESS,
    DECISIONS_CSV,
    EXPECTED_ATTESTER,
    canonical_payload,
    check_decision,
    commitment_hash,
    connect,
    normalize,
)

RESULTS_DIR = os.path.join(LAYER_DIR, "results")

TAMPER_INDEX = 0
TAMPER_PRICE_DELTA = 500


@app.route("/")
def dashboard():
    return render_template("chainproof_dashboard.html")


@app.route("/api/summary")
def summary():
    """Headline stats: real backtest numbers (from strategy_comparison.csv,
    not re-run every request for speed) plus on-chain commitment counts."""
    stats = {}
    comparison_path = os.path.join(RESULTS_DIR, "strategy_comparison.csv")
    if os.path.exists(comparison_path):
        with open(comparison_path) as f:
            for row in csv.DictReader(f):
                if row["symbol"] == "BTC-USD":
                    stats["return_pct"] = round(float(row["best_return"]), 2)
                    stats["sharpe"] = round(float(row["sharpe_ratio"]), 2)
                    stats["win_rate"] = round(float(row["win_rate"]), 2)

    total, succeeded = 0, 0
    log_path = os.path.join(RESULTS_DIR, "chainproof_onchain_log.csv")
    if os.path.exists(log_path):
        with open(log_path) as f:
            for row in csv.DictReader(f):
                total += 1
                if row.get("tx_hash") and row["tx_hash"] != "FAILED":
                    succeeded += 1

    stats["total_commitments"] = total
    stats["succeeded_commitments"] = succeeded
    stats["contract_address"] = CONTRACT_ADDRESS

    stats["signer_address"] = EXPECTED_ATTESTER

    return jsonify(stats)


@app.route("/api/commitments")
def commitments():
    """The on-chain log, straight from the CSV your submission script wrote."""
    log_path = os.path.join(RESULTS_DIR, "chainproof_onchain_log.csv")
    rows = []
    if os.path.exists(log_path):
        with open(log_path) as f:
            for i, row in enumerate(csv.DictReader(f)):
                rows.append({
                    "index": i,
                    "timestamp": row.get("timestamp"),
                    "action": row.get("action"),
                    "price": row.get("price"),
                    "commitment_hash": row.get("commitment_hash"),
                    "tx_hash": row.get("tx_hash"),
                    "block_number": row.get("block_number"),
                })
    return jsonify(rows)


@app.route("/api/run-verification", methods=["POST"])
def run_verification():
    """Live: the same checks as `python verify.py`, returned as JSON."""
    decisions_df = pd.read_csv(DECISIONS_CSV)
    contract = connect()
    count = contract.functions.getCommitmentCount().call()

    results = []
    matches = 0
    for i in range(min(count, len(decisions_df))):
        onchain = contract.functions.getCommitment(i).call()
        hash_ok, signer_ok, recomputed = check_decision(decisions_df.iloc[i], onchain)
        ok = hash_ok and signer_ok
        matches += ok
        results.append({
            "index": i,
            "action": onchain[1],
            "onchain_hash": normalize(onchain[0]),
            "recomputed_hash": recomputed,
            "match": ok,
            "hash_match": hash_ok,
            "signature_valid": signer_ok,
        })

    return jsonify({"results": results, "matches": matches, "total": count})


@app.route("/api/run-tamper-test", methods=["POST"])
def run_tamper_test():
    """Live: a genuine match, then the same decision with its price altered."""
    decisions_df = pd.read_csv(DECISIONS_CSV)
    contract = connect()
    onchain_hash = normalize(contract.functions.getCommitment(TAMPER_INDEX).call()[0])

    row = decisions_df.iloc[TAMPER_INDEX]
    genuine_hash = normalize(commitment_hash(canonical_payload(row)))

    tampered_row = row.copy()
    tampered_row["price"] = float(row["price"]) + TAMPER_PRICE_DELTA
    tampered_hash = normalize(commitment_hash(canonical_payload(tampered_row)))

    return jsonify({
        "index": TAMPER_INDEX,
        "action": row["action"],
        "original_price": float(row["price"]),
        "tampered_price": float(tampered_row["price"]),
        "tamper_delta": TAMPER_PRICE_DELTA,
        "genuine_hash": genuine_hash,
        "tampered_hash": tampered_hash,
        "onchain_hash": onchain_hash,
        "genuine_match": genuine_hash == onchain_hash,
        "tamper_detected": tampered_hash != onchain_hash,
    })


if __name__ == "__main__":
    print("=" * 60)
    print("ChainProof Dashboard")
    print("=" * 60)
    print("Running at: http://localhost:5002")
    print("=" * 60)
    app.run(debug=True, port=5002, use_reloader=False)