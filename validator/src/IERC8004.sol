// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice The subset of the ERC-8004 Identity Registry this stack needs.
/// @dev    IMPORTANT: ERC8004SPEC.md states that `validationRequest` "MUST be
///         called by the owner or operator of agentId", but never specifies
///         which Identity Registry function enforces that. No IIdentityRegistry
///         interface is declared anywhere in the spec, and neither `ownerOf`
///         nor `isAuthorizedOrOwner` is named in it.
///
///         The CC0 reference implementation resolved this by calling
///         `agentExists()`. That function does not exist on the canonical
///         deployed registry (verified against 0x8004A818...BD9e on Sepolia,
///         implementation v2.0.0), so the reference ValidationRegistry reverts
///         against the real thing.
///
///         `isAuthorizedOrOwner(address,uint256)` IS exposed by the deployed
///         registry and is exactly the check the spec describes in prose, so
///         that is what this implementation uses.
interface IIdentityRegistry {
    function isAuthorizedOrOwner(address spender, uint256 agentId) external view returns (bool);
    function ownerOf(uint256 tokenId) external view returns (address);
}

/// @notice The ERC-8004 Validation Registry interface, as specified in
///         ERC8004SPEC.md (Validation Registry section).
interface IValidationRegistry {
    event ValidationRequest(
        address indexed validatorAddress,
        uint256 indexed agentId,
        string requestURI,
        bytes32 indexed requestHash
    );

    event ValidationResponse(
        address indexed validatorAddress,
        uint256 indexed agentId,
        bytes32 indexed requestHash,
        uint8 response,
        string responseURI,
        bytes32 responseHash,
        string tag
    );

    function validationRequest(
        address validatorAddress,
        uint256 agentId,
        string calldata requestURI,
        bytes32 requestHash
    ) external;

    function validationResponse(
        bytes32 requestHash,
        uint8 response,
        string calldata responseURI,
        bytes32 responseHash,
        string calldata tag
    ) external;

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
        );

    function getSummary(uint256 agentId, address[] calldata validatorAddresses, string calldata tag)
        external
        view
        returns (uint64 count, uint8 averageResponse);

    function getAgentValidations(uint256 agentId) external view returns (bytes32[] memory requestHashes);

    function getValidatorRequests(address validatorAddress) external view returns (bytes32[] memory requestHashes);

    function getIdentityRegistry() external view returns (address);
}

/// @notice The subset of ChainProofRegistry the validator reads.
interface IChainProofRegistry {
    function getCommitment(uint256 index)
        external
        view
        returns (
            bytes32 commitmentHash,
            string memory action,
            uint256 timestamp,
            address signer,
            bytes memory signature
        );

    function getCommitmentCount() external view returns (uint256);
}
