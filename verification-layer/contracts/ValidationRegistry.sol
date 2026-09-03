// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IIdentityRegistry, IValidationRegistry} from "./IERC8004.sol";

/// @title  ValidationRegistry
/// @notice An implementation of the ERC-8004 Validation Registry, written
///         against ERC8004SPEC.md (read 2 September 2026).
///
/// @dev    WHY THIS EXISTS
///         No Validation Registry is deployed on any chain. The contracts
///         repo lists Identity and Reputation addresses for 20+ networks and
///         zero Validation Registry addresses; PR #11 removed the official
///         deployments. So there is currently no on-chain venue to publish a
///         validation result into, and this deploys one.
///
/// @dev    DELIBERATE DIFFERENCES FROM THE CANONICAL DEPLOYMENTS, each of
///         which is a design decision rather than an oversight:
///
///         1. NOT UPGRADEABLE. The canonical Identity and Reputation
///            registries are UUPS proxies whose `owner` on both mainnet and
///            Sepolia is a single externally-owned account, with no multisig
///            or timelock in the path. ERC8004SPEC.md never mentions
///            upgradeability, upgrade authority or governance at all. Since
///            this registry's whole purpose is to make verification results
///            durable, an upgrade path that could rewrite their meaning would
///            undercut it. There is no admin here and no way to change the
///            code once deployed.
///
///         2. `initialize()` IS KEPT FOR CONFORMANCE BUT IS NOT THE SAFE
///            OPTION. The spec mandates `initialize(address identityRegistry_)`
///            — an initializer, which is the upgradeable-proxy idiom. On a
///            non-upgradeable contract a constructor is strictly safer: an
///            unguarded initializer can be front-run between deploy and
///            initialise. Note the spec never says the registry is meant to
///            sit behind a proxy; it just assumes it by mandating the
///            initializer pattern. This implementation sets the registry in
///            the constructor AND exposes a guarded `initialize` so that
///            spec-conformant callers still work.
///
///         3. DUPLICATE `requestHash` REVERTS. The spec says `requestHash`
///            "identifies the request" but never states it must be unique,
///            nor what should happen if `validationRequest` is called twice
///            with the same hash — including by a different agent. Silently
///            overwriting would let any agent hijack another's pending
///            request, so this reverts. Documented because it is a genuine
///            ambiguity an implementer has to resolve.
contract ValidationRegistry is IValidationRegistry {
    struct Validation {
        address validatorAddress;
        uint256 agentId;
        uint8 response;
        bytes32 responseHash;
        string tag;
        uint256 lastUpdate;
        bool requested;
        bool responded;
    }

    /// @dev requestHash => validation record. Per the spec, the contract
    ///      stores requestHash, validatorAddress, agentId, response,
    ///      responseHash, lastUpdate and tag for on-chain querying.
    mapping(bytes32 => Validation) private _validations;

    mapping(uint256 => bytes32[]) private _agentValidations;
    mapping(address => bytes32[]) private _validatorRequests;

    address private _identityRegistry;
    bool private _initialized;

    error AlreadyInitialized();
    error ZeroAddress();
    error NotAuthorizedForAgent(address caller, uint256 agentId);
    error RequestAlreadyExists(bytes32 requestHash);
    error UnknownRequest(bytes32 requestHash);
    error NotDesignatedValidator(address caller, address expected);
    error ResponseOutOfRange(uint8 response);

    constructor(address identityRegistry_) {
        if (identityRegistry_ == address(0)) revert ZeroAddress();
        _identityRegistry = identityRegistry_;
        _initialized = true;
    }

    /// @notice Present for spec conformance. The constructor has already run,
    ///         so this always reverts on a deployed instance.
    function initialize(address identityRegistry_) external {
        if (_initialized) revert AlreadyInitialized();
        if (identityRegistry_ == address(0)) revert ZeroAddress();
        _identityRegistry = identityRegistry_;
        _initialized = true;
    }

    function getIdentityRegistry() external view returns (address) {
        return _identityRegistry;
    }

    // ---------------------------------------------------------------- request

    /// @inheritdoc IValidationRegistry
    /// @dev The spec requires the caller to be the owner or operator of
    ///      agentId but does not say how to check it. See IERC8004.sol.
    function validationRequest(
        address validatorAddress,
        uint256 agentId,
        string calldata requestURI,
        bytes32 requestHash
    ) external {
        if (!IIdentityRegistry(_identityRegistry).isAuthorizedOrOwner(msg.sender, agentId)) {
            revert NotAuthorizedForAgent(msg.sender, agentId);
        }
        if (validatorAddress == address(0)) revert ZeroAddress();
        if (_validations[requestHash].requested) revert RequestAlreadyExists(requestHash);

        Validation storage v = _validations[requestHash];
        v.validatorAddress = validatorAddress;
        v.agentId = agentId;
        v.requested = true;
        v.lastUpdate = block.timestamp;

        _agentValidations[agentId].push(requestHash);
        _validatorRequests[validatorAddress].push(requestHash);

        emit ValidationRequest(validatorAddress, agentId, requestURI, requestHash);
    }

    // --------------------------------------------------------------- response

    /// @inheritdoc IValidationRegistry
    /// @dev May be called repeatedly for the same requestHash — the spec
    ///      allows progressive validation states. Later calls overwrite the
    ///      stored response and bump lastUpdate; the full history stays in
    ///      the event log.
    function validationResponse(
        bytes32 requestHash,
        uint8 response,
        string calldata responseURI,
        bytes32 responseHash,
        string calldata tag
    ) external {
        Validation storage v = _validations[requestHash];
        if (!v.requested) revert UnknownRequest(requestHash);
        if (msg.sender != v.validatorAddress) revert NotDesignatedValidator(msg.sender, v.validatorAddress);
        if (response > 100) revert ResponseOutOfRange(response);

        v.response = response;
        v.responseHash = responseHash;
        v.tag = tag;
        v.lastUpdate = block.timestamp;
        v.responded = true;

        emit ValidationResponse(v.validatorAddress, v.agentId, requestHash, response, responseURI, responseHash, tag);
    }

    // ------------------------------------------------------------------ reads

    function getValidationStatus(bytes32 requestHash)
        external
        view
        returns (
            address validatorAddress,
            uint256 agentId,
            uint8 response,
            bytes32 responseHash,
            string memory tag,
            uint256 lastUpdate
        )
    {
        Validation storage v = _validations[requestHash];
        if (!v.requested) revert UnknownRequest(requestHash);
        return (v.validatorAddress, v.agentId, v.response, v.responseHash, v.tag, v.lastUpdate);
    }

    /// @notice Aggregated statistics for an agent. agentId is mandatory;
    ///         validatorAddresses and tag are optional filters — pass an
    ///         empty array and an empty string to include everything.
    /// @dev    Only requests that have received a response are counted.
    ///         Unanswered requests are excluded rather than counted as zero,
    ///         which would be indistinguishable from a failing verdict.
    function getSummary(uint256 agentId, address[] calldata validatorAddresses, string calldata tag)
        external
        view
        returns (uint64 count, uint8 averageResponse)
    {
        bytes32[] storage hashes = _agentValidations[agentId];
        bytes32 tagHash = keccak256(bytes(tag));
        bool filterTag = bytes(tag).length > 0;
        bool filterValidator = validatorAddresses.length > 0;

        uint256 total;
        uint64 n;

        for (uint256 i = 0; i < hashes.length; i++) {
            Validation storage v = _validations[hashes[i]];
            if (!v.responded) continue;
            if (filterTag && keccak256(bytes(v.tag)) != tagHash) continue;
            if (filterValidator && !_contains(validatorAddresses, v.validatorAddress)) continue;

            total += v.response;
            n++;
        }

        if (n == 0) return (0, 0);
        return (n, uint8(total / n));
    }

    function getAgentValidations(uint256 agentId) external view returns (bytes32[] memory) {
        return _agentValidations[agentId];
    }

    function getValidatorRequests(address validatorAddress) external view returns (bytes32[] memory) {
        return _validatorRequests[validatorAddress];
    }

    function _contains(address[] calldata haystack, address needle) private pure returns (bool) {
        for (uint256 i = 0; i < haystack.length; i++) {
            if (haystack[i] == needle) return true;
        }
        return false;
    }
}
