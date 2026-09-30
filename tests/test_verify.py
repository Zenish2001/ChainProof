"""Tests for the ChainProof verifier, run against the real published data.

These need no network: the committed hashes and signatures are read from
verification-layer/results/. Run from the repository root:  pytest tests
"""

import os
import sys

import pytest

pytest.importorskip("web3")
pytest.importorskip("eth_account")

import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYER = os.path.join(ROOT, "verification-layer")
sys.path.insert(0, LAYER)

from verify import (  # noqa: E402
    DECISIONS_CSV,
    EXPECTED_ATTESTER,
    canonical_payload,
    check_decision,
    commitment_hash,
    normalize,
    recover_signer,
)

DECISIONS = pd.read_csv(DECISIONS_CSV)
COMMITMENTS = pd.read_csv(os.path.join(LAYER, "results", "chainproof_commitments.csv"))


def onchain_record(i, signer=None):
    """The tuple ChainProofRegistry.getCommitment(i) returns, built from the
    published commitments file."""
    c = COMMITMENTS.iloc[i]
    return (
        bytes.fromhex(normalize(c["commitment_hash"])),
        c["action"],
        0,
        signer or c["signer_address"],
        bytes.fromhex(normalize(c["signature"])),
    )


def hash_of(row):
    return normalize(commitment_hash(canonical_payload(row)))


def test_every_published_decision_hashes_to_its_commitment():
    assert len(DECISIONS) == len(COMMITMENTS) == 30
    for i in range(len(DECISIONS)):
        assert hash_of(DECISIONS.iloc[i]) == normalize(COMMITMENTS.iloc[i]["commitment_hash"])


def test_every_commitment_is_signed_by_the_attester():
    for i in range(len(COMMITMENTS)):
        c = COMMITMENTS.iloc[i]
        signer = recover_signer(bytes.fromhex(normalize(c["commitment_hash"])),
                                bytes.fromhex(normalize(c["signature"])))
        assert signer.lower() == EXPECTED_ATTESTER.lower()


def test_changing_any_committed_field_changes_the_hash():
    row = DECISIONS.iloc[0]
    original = hash_of(row)
    edits = {
        "timestamp": "2024-04-14 00:00:00+00:00",
        "role": "EXIT",
        "action": "SELL",
        "price": float(row["price"]) + 0.01,
        "signal_strength": 75,
        "overall_signal": "SELL",
    }
    for col in [c for c in DECISIONS.columns if c.startswith("ind_")]:
        edits[col] = "SELL" if row[col] != "SELL" else "BUY"

    for col, value in edits.items():
        tampered = row.copy()
        tampered[col] = value
        assert hash_of(tampered) != original, f"editing {col} did not change the hash"


def test_hash_does_not_depend_on_column_order():
    shuffled = DECISIONS[list(reversed(DECISIONS.columns))]
    for i in range(len(DECISIONS)):
        assert hash_of(shuffled.iloc[i]) == hash_of(DECISIONS.iloc[i])


def test_check_decision_accepts_genuine_and_rejects_tampered_rows():
    row = DECISIONS.iloc[5]
    assert check_decision(row, onchain_record(5))[:2] == (True, True)

    tampered = row.copy()
    tampered["price"] = float(row["price"]) + 500
    hash_ok, signer_ok, _ = check_decision(tampered, onchain_record(5))
    assert not hash_ok and signer_ok


def test_check_decision_rejects_a_record_claiming_another_signer():
    forged = onchain_record(3, signer="0x000000000000000000000000000000000000dEaD")
    hash_ok, signer_ok, _ = check_decision(DECISIONS.iloc[3], forged)
    assert hash_ok and not signer_ok


def test_check_decision_rejects_a_signature_from_another_commitment():
    genuine = onchain_record(3)
    borrowed = genuine[:4] + (onchain_record(4)[4],)
    hash_ok, signer_ok, _ = check_decision(DECISIONS.iloc[3], borrowed)
    assert hash_ok and not signer_ok
