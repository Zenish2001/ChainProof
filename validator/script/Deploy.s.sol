// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {ValidationRegistry} from "../src/ValidationRegistry.sol";
import {ChainProofValidator} from "../src/ChainProofValidator.sol";

/// @notice Deploys the ERC-8004 Validation Registry and the ChainProof
///         validator to Ethereum Sepolia.
///
/// Run:
///   forge script script/Deploy.s.sol:Deploy \
///     --rpc-url https://ethereum-sepolia-rpc.publicnode.com \
///     --broadcast --interactive 1
///
/// Drop --broadcast for a dry run first.
contract Deploy is Script {
    /// @dev Canonical ERC-8004 Identity Registry. Same address on Sepolia and
    ///      mainnet; implementation v2.0.0 at time of writing.
    address constant IDENTITY_REGISTRY = 0x8004A818BFB912233c491871b3d84c89A494BD9e;

    /// @dev ChainProof's existing commitment log, already live on Sepolia.
    address constant CHAINPROOF_REGISTRY = 0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955;

    /// @dev The address permitted to publish verdicts. Set to the agent owner,
    ///      which already holds Sepolia gas. The attestation key that signs
    ///      commitments off-chain (0xBd121B7396...) is deliberately NOT the
    ///      operator: signing a commitment and publishing a verdict about it
    ///      are different authorities and should not share a key.
    address constant OPERATOR = 0x7ACad346325EC88a8CC9d01C99aeAd2851fB939B;

    function run() external {
        vm.startBroadcast();

        ValidationRegistry validationRegistry = new ValidationRegistry(IDENTITY_REGISTRY);
        console.log("ValidationRegistry   :", address(validationRegistry));

        ChainProofValidator validator =
            new ChainProofValidator(address(validationRegistry), CHAINPROOF_REGISTRY, OPERATOR);
        console.log("ChainProofValidator  :", address(validator));

        vm.stopBroadcast();

        console.log("");
        console.log("Identity Registry    :", validationRegistry.getIdentityRegistry());
        console.log("ChainProof Registry  :", CHAINPROOF_REGISTRY);
        console.log("Operator             :", validator.operator());
        console.log("");
        console.log("Record both addresses, then run RequestAndPublish.s.sol");
    }
}
