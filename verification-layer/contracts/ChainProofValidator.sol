// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IValidationRegistry, IChainProofRegistry} from "./IERC8004.sol";

/// @title  ChainProofValidator
/// @notice The ERC-8004 validator for ChainProof. Publishes deterministic-replay
///         verification results into a Validation Registry.
///
/// @dev    WHAT THIS PROVES AND WHAT IT DOES NOT
///
///         The verification itself is off-chain and unavoidably so: it re-runs
///         a trading strategy over historical price data, which cannot execute
///         on-chain. This contract does not re-derive the verdict.
///
///         What it DOES enforce on-chain is a binding that the bare spec flow
///         leaves open. Under ERC-8004 alone, a validator is simply an address
///         that posts a number between 0 and 100 against a requestHash; nothing
///         constrains that hash to correspond to anything real. Here, a verdict
///         can only be published for a requestHash that already exists as a
///         commitment in ChainProofRegistry. A verdict about a decision that was
///         never committed is not expressible.
///
///         This works because the two hashes are the same object. ERC8004SPEC.md
///         defines requestHash as keccak256 of the request payload; ChainProof's
///         commitmentHash is keccak256 over a decision's full input snapshot —
///         price, every indicator value, the decision, and the active risk
///         parameters. So requestHash == commitmentHash by construction, and the
///         binding is a storage read rather than a convention.
///
/// @dev    SCOPE, STATED HONESTLY
///         A passing verdict here means: this commitment exists on-chain, and an
///         off-chain replay of the unmodified strategy code under the declared
///         parameters reproduced it. It does not mean the strategy is profitable,
///         that the parameters were not selected post-hoc from a comparison
///         sweep, or that the committed set is complete. The last of those is a
///         general property of the ERC-8004 reputation and validation model:
///         hashes prove records were not rewritten, never that none are missing.
///         ChainProof mitigates it only because deterministic replay lets a
///         verifier derive the full expected decision sequence independently.
contract ChainProofValidator {
    IValidationRegistry public immutable validationRegistry;
    IChainProofRegistry public immutable chainProofRegistry;

    /// @notice The attestation operator permitted to publish verdicts.
    address public operator;

    /// @notice Emitted alongside the registry's own ValidationResponse, adding
    ///         the commitment index the verdict was bound to.
    event VerdictPublished(
        bytes32 indexed requestHash, uint256 indexed commitmentIndex, uint8 response, string tag
    );

    event OperatorTransferred(address indexed previousOperator, address indexed newOperator);

    error NotOperator(address caller);
    error ZeroAddress();
    error CommitmentIndexOutOfRange(uint256 index, uint256 count);
    error CommitmentMismatch(bytes32 requestHash, bytes32 committedHash);

    modifier onlyOperator() {
        if (msg.sender != operator) revert NotOperator(msg.sender);
        _;
    }

    constructor(address validationRegistry_, address chainProofRegistry_, address operator_) {
        if (validationRegistry_ == address(0) || chainProofRegistry_ == address(0) || operator_ == address(0)) {
            revert ZeroAddress();
        }
        validationRegistry = IValidationRegistry(validationRegistry_);
        chainProofRegistry = IChainProofRegistry(chainProofRegistry_);
        operator = operator_;
    }

    /// @notice Publish a verification result, bound to an existing commitment.
    /// @param requestHash      The requestHash from the ValidationRequest. Must
    ///                         equal the commitmentHash stored at commitmentIndex.
    /// @param commitmentIndex  Index into ChainProofRegistry's commitment array.
    /// @param response         0-100. Use 100 for a reproduced commitment and 0
    ///                         for a mismatch; intermediate values are reserved
    ///                         for partial replays.
    /// @param responseURI      Off-chain evidence: the replay report.
    /// @param responseHash     keccak256 of that report.
    /// @param tag              Categorisation. "deterministic-replay" for this
    ///                         validator. See note below on tag vocabulary.
    ///
    /// @dev The spec leaves `tag` a free string, so a TEE attestation, a staked
    ///      re-execution and a subjective judgment all land in the same registry
    ///      as indistinguishable integers with very different failure modes and
    ///      accountability. Consumers cannot filter getSummary by kind of
    ///      assurance. This validator always tags "deterministic-replay" so that
    ///      its results are at least separable by a caller who knows to look.
    function publishVerdict(
        bytes32 requestHash,
        uint256 commitmentIndex,
        uint8 response,
        string calldata responseURI,
        bytes32 responseHash,
        string calldata tag
    ) external onlyOperator {
        uint256 count = chainProofRegistry.getCommitmentCount();
        if (commitmentIndex >= count) revert CommitmentIndexOutOfRange(commitmentIndex, count);

        (bytes32 committedHash,,,,) = chainProofRegistry.getCommitment(commitmentIndex);
        if (committedHash != requestHash) revert CommitmentMismatch(requestHash, committedHash);

        validationRegistry.validationResponse(requestHash, response, responseURI, responseHash, tag);

        emit VerdictPublished(requestHash, commitmentIndex, response, tag);
    }

    function transferOperator(address newOperator) external onlyOperator {
        if (newOperator == address(0)) revert ZeroAddress();
        emit OperatorTransferred(operator, newOperator);
        operator = newOperator;
    }
}
