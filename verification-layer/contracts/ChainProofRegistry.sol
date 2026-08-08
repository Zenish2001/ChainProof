// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title ChainProofRegistry
/// @notice A minimal on-chain log of trading-decision commitments. Each
///         commitment is a keccak256 hash (computed off-chain by
///         commit_and_sign.py) covering a decision's inputs, the decision
///         itself, and the active risk parameters -- plus a signature
///         from a local attestation key, standing in for a full TEE
///         attestation.
/// @dev    Deliberately minimal per the project's 5-hour MVP scope: no
///         upgradability, no access control beyond none (anyone can
///         submit, since this is a personal verification log, not a
///         multi-party system), no multi-chain support.
contract ChainProofRegistry {
    struct Commitment {
        bytes32 commitmentHash;
        string action;
        uint256 timestamp;
        address signer;
        bytes signature;
    }

    Commitment[] public commitments;

    event CommitmentSubmitted(
        uint256 indexed index,
        bytes32 indexed commitmentHash,
        string action,
        uint256 timestamp,
        address indexed signer
    );

    function submitCommitment(
        bytes32 commitmentHash,
        string calldata action,
        uint256 timestamp,
        address signer,
        bytes calldata signature
    ) external returns (uint256 index) {
        commitments.push(Commitment({
            commitmentHash: commitmentHash,
            action: action,
            timestamp: timestamp,
            signer: signer,
            signature: signature
        }));

        index = commitments.length - 1;

        emit CommitmentSubmitted(index, commitmentHash, action, timestamp, signer);
    }

    function getCommitmentCount() external view returns (uint256) {
        return commitments.length;
    }

    function getCommitment(uint256 index) external view returns (
        bytes32 commitmentHash,
        string memory action,
        uint256 timestamp,
        address signer,
        bytes memory signature
    ) {
        Commitment storage c = commitments[index];
        return (c.commitmentHash, c.action, c.timestamp, c.signer, c.signature);
    }
}
