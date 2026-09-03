// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {IValidationRegistry} from "../src/IERC8004.sol";
import {ChainProofValidator} from "../src/ChainProofValidator.sol";

/// @notice Runs one complete ERC-8004 validation cycle for ChainProof:
///         request, then verdict, then read back the stored status.
///
/// Run:
///   VALIDATION_REGISTRY=0x... VALIDATOR=0x... \
///   forge script script/RequestAndPublish.s.sol:RequestAndPublish \
///     --rpc-url https://ethereum-sepolia-rpc.publicnode.com \
///     --broadcast --interactive 1
///
/// @dev Both transactions are sent by the same key here, but they exercise two
///      distinct authorities the spec keeps separate:
///        - validationRequest MUST come from the owner or operator of agentId,
///          checked against the Identity Registry via isAuthorizedOrOwner.
///        - validationResponse MUST come from the validatorAddress named in the
///          request — which is the ChainProofValidator contract, not an EOA.
///          The contract is what calls the registry; the operator only
///          authorises it to.
contract RequestAndPublish is Script {
    uint256 constant AGENT_ID = 9896;

    /// @dev commitmentHash of ChainProofRegistry commitment #0 — a BUY decision
    ///      at unix 1712966400. Doubles as the ERC-8004 requestHash, since both
    ///      are keccak256 over the same decision payload.
    bytes32 constant REQUEST_HASH = 0x6c87efc43ec1281875205c284b67657bc6db5d81c6e746eb146a7766d1586305;
    uint256 constant COMMITMENT_INDEX = 0;

    /// @dev What the validator is asked to check. Points at the replay dataset
    ///      and the strategy code needed to reproduce the commitment.
    string constant REQUEST_URI = "https://github.com/Zenish2001/ChainProof/tree/main/verification-layer";

    /// @dev Evidence for the verdict. Replace with the published replay report
    ///      once it is hosted; responseHash stays zero while the report is not
    ///      content-addressed (the spec marks both fields optional).
    string constant RESPONSE_URI = "https://github.com/Zenish2001/ChainProof/tree/main/verification-layer";
    bytes32 constant RESPONSE_HASH = bytes32(0);

    /// @dev Free-form in the spec, which is a gap: a TEE attestation, a staked
    ///      re-execution and an LLM judgment all land here as indistinguishable
    ///      integers. Tagging the assurance type is the only way a consumer can
    ///      tell them apart.
    string constant TAG = "deterministic-replay";

    function run() external {
        IValidationRegistry validationRegistry = IValidationRegistry(vm.envAddress("VALIDATION_REGISTRY"));
        ChainProofValidator validator = ChainProofValidator(vm.envAddress("VALIDATOR"));

        vm.startBroadcast();

        validationRegistry.validationRequest(address(validator), AGENT_ID, REQUEST_URI, REQUEST_HASH);
        console.log("ValidationRequest submitted for agent", AGENT_ID);

        // response = 100: the off-chain replay reproduced this commitment
        // exactly. The contract independently checks REQUEST_HASH matches the
        // commitment stored at COMMITMENT_INDEX before the verdict is accepted.
        validator.publishVerdict(REQUEST_HASH, COMMITMENT_INDEX, 100, RESPONSE_URI, RESPONSE_HASH, TAG);
        console.log("Verdict published");

        vm.stopBroadcast();

        (
            address validatorAddress,
            uint256 agentId,
            uint8 response,
            bytes32 responseHash,
            string memory tag,
            uint256 lastUpdate
        ) = validationRegistry.getValidationStatus(REQUEST_HASH);

        console.log("");
        console.log("--- getValidationStatus ---");
        console.log("validatorAddress :", validatorAddress);
        console.log("agentId          :", agentId);
        console.log("response         :", response);
        console.log("tag              :", tag);
        console.log("lastUpdate       :", lastUpdate);
        console.logBytes32(responseHash);

        (uint64 count, uint8 averageResponse) =
            validationRegistry.getSummary(AGENT_ID, new address[](0), "");
        console.log("");
        console.log("--- getSummary ---");
        console.log("count            :", count);
        console.log("averageResponse  :", averageResponse);
    }
}
