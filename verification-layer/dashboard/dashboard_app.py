"""
dashboard_app.py

Flask backend for the ChainProof results dashboard. Deliberately reuses
verifier.py and tamper_test.py's own functions directly -- clicking
"Run Verification" or "Run Tamper Test" on the dashboard runs the real
independent verification live, the same code paths you already ran
successfully from the terminal.

Run from the chainproof/dashboard/ folder:
    python dashboard_app.py
Then open http://localhost:5002
"""

import csv
import os
import sys

from flask import Flask, jsonify, render_template

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# IMPORTANT: create the Flask app *before* changing the working directory.
# Flask determines where its static/ and templates/ folders live at the
# moment Flask(__name__) is called, based on the current working directory
# at that instant. If os.chdir() ran first, Flask would resolve its static
# folder relative to the wrong directory and every CSS/JS request would
# silently 404 -- which is exactly what was happening.
app = Flask(__name__)

# Force the working directory to the project root, regardless of where this
# script is launched from -- otherwise relative paths like
# 'data/trading_bot.db' silently create a fresh empty database instead of
# finding the real one. dashboard_app.py now lives in chainproof/dashboard/,
# so the project root is two levels up.
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
os.chdir(PROJECT_ROOT)

from verifier import (
    CONTRACT_ADDRESS,
    canonical_payload,
    commitment_hash,
    fetch_onchain_commitments,
    regenerate_decisions_independently,
)
from tamper_test import TAMPER_INDEX, TAMPER_PRICE_DELTA

# chainproof/dashboard/dashboard_app.py -> data/ is two levels up, then into data/
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

# attestation_key.json lives in chainproof/, one level up from chainproof/dashboard/
ATTESTATION_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "attestation_key.json")


@app.route("/")
def dashboard():
    return render_template("chainproof_dashboard.html")


@app.route("/api/summary")
def summary():
    """Headline stats: real backtest numbers (from strategy_comparison.csv,
    not re-run every request for speed) plus on-chain commitment counts."""
    stats = {}
    comparison_path = os.path.join(DATA_DIR, "strategy_comparison.csv")
    if os.path.exists(comparison_path):
        with open(comparison_path) as f:
            for row in csv.DictReader(f):
                if row["symbol"] == "BTC-USD":
                    stats["return_pct"] = round(float(row["best_return"]), 2)
                    stats["sharpe"] = round(float(row["sharpe_ratio"]), 2)
                    stats["win_rate"] = round(float(row["win_rate"]), 2)

    total, succeeded = 0, 0
    log_path = os.path.join(DATA_DIR, "chainproof_onchain_log.csv")
    if os.path.exists(log_path):
        with open(log_path) as f:
            for row in csv.DictReader(f):
                total += 1
                if row.get("tx_hash") and row["tx_hash"] != "FAILED":
                    succeeded += 1

    stats["total_commitments"] = total
    stats["succeeded_commitments"] = succeeded
    stats["contract_address"] = CONTRACT_ADDRESS

    key_path = ATTESTATION_KEY_PATH
    if os.path.exists(key_path):
        import json
        with open(key_path) as f:
            stats["signer_address"] = json.load(f).get("address")

    return jsonify(stats)


@app.route("/api/commitments")
def commitments():
    """The on-chain log, straight from the CSV your submission script wrote."""
    log_path = os.path.join(DATA_DIR, "chainproof_onchain_log.csv")
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
    """Live: re-runs the actual strategy code and compares against the
    live contract, exactly like `python verifier.py` does from the
    terminal -- just returned as JSON for the dashboard to render."""
    decisions_df = regenerate_decisions_independently()
    onchain = fetch_onchain_commitments()

    results = []
    matches = 0
    for i, entry in enumerate(onchain):
        if i >= len(decisions_df):
            continue
        row = decisions_df.iloc[i]
        recomputed = commitment_hash(canonical_payload(row))
        ok = recomputed == entry["commitment_hash"]
        matches += ok
        results.append({
            "index": i,
            "action": entry["action"],
            "onchain_hash": entry["commitment_hash"],
            "recomputed_hash": recomputed,
            "match": ok,
        })

    return jsonify({"results": results, "matches": matches, "total": len(onchain)})


@app.route("/api/run-tamper-test", methods=["POST"])
def run_tamper_test():
    """Live: the same two-part check as tamper_test.py -- a genuine match,
    then the same decision with its price altered, showing the mismatch."""
    decisions_df = regenerate_decisions_independently()
    onchain = fetch_onchain_commitments()

    row = decisions_df.iloc[TAMPER_INDEX]
    onchain_hash = onchain[TAMPER_INDEX]["commitment_hash"]

    genuine_hash = commitment_hash(canonical_payload(row))
    genuine_ok = genuine_hash == onchain_hash

    tampered_row = row.copy()
    tampered_row["price"] = tampered_row["price"] + TAMPER_PRICE_DELTA
    tampered_hash = commitment_hash(canonical_payload(tampered_row))
    tamper_detected = tampered_hash != onchain_hash

    return jsonify({
        "index": int(TAMPER_INDEX),
        "action": row["action"],
        "original_price": float(row["price"]),
        "tampered_price": float(tampered_row["price"]),
        "tamper_delta": TAMPER_PRICE_DELTA,
        "genuine_hash": genuine_hash,
        "tampered_hash": tampered_hash,
        "onchain_hash": onchain_hash,
        "genuine_match": genuine_ok,
        "tamper_detected": tamper_detected,
    })


if __name__ == "__main__":
    print("=" * 60)
    print("ChainProof Dashboard")
    print("=" * 60)
    print("Running at: http://localhost:5002")
    print("=" * 60)
    app.run(debug=True, port=5002, use_reloader=False)