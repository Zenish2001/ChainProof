// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {ValidationRegistry} from "../src/ValidationRegistry.sol";
import {ChainProofValidator} from "../src/ChainProofValidator.sol";
import {IIdentityRegistry, IChainProofRegistry} from "../src/IERC8004.sol";

/// @notice Fork tests against live Sepolia state.
///
/// These run against the real canonical Identity Registry and the real
/// ChainProofRegistry rather than mocks. That matters: the central claim being
/// tested is about how the deployed registry actually behaves, and a mock would
/// only assert what I assumed it does.
///
/// Run:
///   forge test --fork-url https://ethereum-sepolia-rpc.publicnode.com -vv
contract ValidationRegistryForkTest is Test {
    address constant IDENTITY_REGISTRY = 0x8004A818BFB912233c491871b3d84c89A494BD9e;
    address constant CHAINPROOF_REGISTRY = 0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955;

    uint256 constant AGENT_ID = 9896;
    address constant AGENT_OWNER = 0x7ACad346325EC88a8CC9d01C99aeAd2851fB939B;

    /// @dev commitment #0 in ChainProofRegistry — a BUY at unix 1712966400.
    bytes32 constant COMMITMENT_0 = 0x6c87efc43ec1281875205c284b67657bc6db5d81c6e746eb146a7766d1586305;

    ValidationRegistry registry;
    ChainProofValidator validator;

    address operator = AGENT_OWNER;
    address stranger = address(0xBEEF);

    function setUp() public {
        registry = new ValidationRegistry(IDENTITY_REGISTRY);
        validator = new ChainProofValidator(address(registry), CHAINPROOF_REGISTRY, operator);
    }

    // ------------------------------------------------------------------
    // The authorization gap (KG-30)
    // ------------------------------------------------------------------

    /// @notice The canonical registry does NOT expose agentExists().
    /// @dev This is the whole reason the CC0 reference ValidationRegistry
    ///      reverts in production: it calls a function that is not there.
    ///      Asserted by raw call so the test does not depend on an interface
    ///      declaring a function that does not exist.
    function test_CanonicalRegistry_DoesNotExpose_agentExists() public view {
        (bool ok,) = IDENTITY_REGISTRY.staticcall(abi.encodeWithSignature("agentExists(uint256)", AGENT_ID));
        assertFalse(ok, "agentExists unexpectedly present - KG-30 needs revisiting");
    }

    /// @notice isAuthorizedOrOwner IS exposed and returns true for the owner.
    ///         This is the function the spec describes in prose but never names.
    function test_CanonicalRegistry_Exposes_isAuthorizedOrOwner() public view {
        assertTrue(IIdentityRegistry(IDENTITY_REGISTRY).isAuthorizedOrOwner(AGENT_OWNER, AGENT_ID));
        assertFalse(IIdentityRegistry(IDENTITY_REGISTRY).isAuthorizedOrOwner(stranger, AGENT_ID));
    }

    function test_ValidationRequest_FromOwner_Succeeds() public {
        vm.prank(AGENT_OWNER);
        registry.validationRequest(address(validator), AGENT_ID, "ipfs://request", COMMITMENT_0);

        (address v, uint256 id,,,, uint256 lastUpdate) = registry.getValidationStatus(COMMITMENT_0);
        assertEq(v, address(validator));
        assertEq(id, AGENT_ID);
        assertEq(lastUpdate, block.timestamp);
    }

    function test_ValidationRequest_FromStranger_Reverts() public {
        vm.prank(stranger);
        vm.expectRevert(
            abi.encodeWithSelector(ValidationRegistry.NotAuthorizedForAgent.selector, stranger, AGENT_ID)
        );
        registry.validationRequest(address(validator), AGENT_ID, "ipfs://request", COMMITMENT_0);
    }

    // ------------------------------------------------------------------
    // Request uniqueness — a spec ambiguity, resolved by reverting
    // ------------------------------------------------------------------

    /// @dev The spec says requestHash "identifies the request" but never states
    ///      it must be unique, nor what happens on a repeat. Silent overwrite
    ///      would let a second agent hijack a pending request, so this reverts.
    function test_DuplicateRequestHash_Reverts() public {
        vm.startPrank(AGENT_OWNER);
        registry.validationRequest(address(validator), AGENT_ID, "ipfs://request", COMMITMENT_0);

        vm.expectRevert(abi.encodeWithSelector(ValidationRegistry.RequestAlreadyExists.selector, COMMITMENT_0));
        registry.validationRequest(address(validator), AGENT_ID, "ipfs://again", COMMITMENT_0);
        vm.stopPrank();
    }

    // ------------------------------------------------------------------
    // Response authorization
    // ------------------------------------------------------------------

    function test_Response_FromNonValidator_Reverts() public {
        _request();

        vm.prank(stranger);
        vm.expectRevert(
            abi.encodeWithSelector(
                ValidationRegistry.NotDesignatedValidator.selector, stranger, address(validator)
            )
        );
        registry.validationResponse(COMMITMENT_0, 100, "", bytes32(0), "");
    }

    /// @dev Even the agent owner cannot answer their own validation request.
    function test_Response_FromAgentOwner_Reverts() public {
        _request();

        vm.prank(AGENT_OWNER);
        vm.expectRevert();
        registry.validationResponse(COMMITMENT_0, 100, "", bytes32(0), "");
    }

    function test_Response_ForUnknownRequest_Reverts() public {
        bytes32 unknown = keccak256("never requested");
        vm.prank(address(validator));
        vm.expectRevert(abi.encodeWithSelector(ValidationRegistry.UnknownRequest.selector, unknown));
        registry.validationResponse(unknown, 100, "", bytes32(0), "");
    }

    function test_Response_OutOfRange_Reverts() public {
        _request();
        vm.prank(address(validator));
        vm.expectRevert(abi.encodeWithSelector(ValidationRegistry.ResponseOutOfRange.selector, uint8(101)));
        registry.validationResponse(COMMITMENT_0, 101, "", bytes32(0), "");
    }

    /// @dev The spec explicitly allows repeated responses per requestHash for
    ///      progressive validation states. Later calls must update, not append.
    function test_RepeatedResponses_UpdateInPlace() public {
        _request();

        vm.startPrank(operator);
        validator.publishVerdict(COMMITMENT_0, 0, 60, "", bytes32(0), "soft-finality");
        (,, uint8 first,,,) = registry.getValidationStatus(COMMITMENT_0);
        assertEq(first, 60);

        vm.warp(block.timestamp + 1 hours);
        validator.publishVerdict(COMMITMENT_0, 0, 100, "", bytes32(0), "hard-finality");
        vm.stopPrank();

        (,, uint8 second,, string memory tag, uint256 lastUpdate) = registry.getValidationStatus(COMMITMENT_0);
        assertEq(second, 100);
        assertEq(tag, "hard-finality");
        assertEq(lastUpdate, block.timestamp);

        (uint64 count,) = registry.getSummary(AGENT_ID, new address[](0), "");
        assertEq(count, 1, "repeated responses must not inflate the count");
    }

    // ------------------------------------------------------------------
    // The commitment binding
    // ------------------------------------------------------------------

    function test_PublishVerdict_BindsToRealCommitment() public {
        _request();
        vm.prank(operator);
        validator.publishVerdict(COMMITMENT_0, 0, 100, "ipfs://report", bytes32(0), "deterministic-replay");

        (,, uint8 response,, string memory tag,) = registry.getValidationStatus(COMMITMENT_0);
        assertEq(response, 100);
        assertEq(tag, "deterministic-replay");
    }

    /// @notice A verdict about a decision that was never committed is not
    ///         expressible. This is the property the bare spec does not give you.
    function test_PublishVerdict_HashNotMatchingCommitment_Reverts() public {
        bytes32 fabricated = keccak256("a trade that never happened");

        vm.prank(AGENT_OWNER);
        registry.validationRequest(address(validator), AGENT_ID, "ipfs://request", fabricated);

        (bytes32 actual,,,,) = IChainProofRegistry(CHAINPROOF_REGISTRY).getCommitment(0);

        vm.prank(operator);
        vm.expectRevert(
            abi.encodeWithSelector(ChainProofValidator.CommitmentMismatch.selector, fabricated, actual)
        );
        validator.publishVerdict(fabricated, 0, 100, "", bytes32(0), "deterministic-replay");
    }

    function test_PublishVerdict_IndexOutOfRange_Reverts() public {
        _request();
        uint256 count = IChainProofRegistry(CHAINPROOF_REGISTRY).getCommitmentCount();

        vm.prank(operator);
        vm.expectRevert(
            abi.encodeWithSelector(ChainProofValidator.CommitmentIndexOutOfRange.selector, count, count)
        );
        validator.publishVerdict(COMMITMENT_0, count, 100, "", bytes32(0), "");
    }

    function test_PublishVerdict_FromNonOperator_Reverts() public {
        _request();
        vm.prank(stranger);
        vm.expectRevert(abi.encodeWithSelector(ChainProofValidator.NotOperator.selector, stranger));
        validator.publishVerdict(COMMITMENT_0, 0, 100, "", bytes32(0), "");
    }

    // ------------------------------------------------------------------
    // Summary semantics
    // ------------------------------------------------------------------

    /// @dev An unanswered request must not be counted as a zero. Zero is a
    ///      failing verdict; absent is not the same thing, and conflating them
    ///      would let a pending validation read as a failure.
    function test_Summary_ExcludesUnansweredRequests() public {
        _request();
        (uint64 count, uint8 avg) = registry.getSummary(AGENT_ID, new address[](0), "");
        assertEq(count, 0);
        assertEq(avg, 0);
    }

    function test_Summary_FiltersByValidator() public {
        _request();
        vm.prank(operator);
        validator.publishVerdict(COMMITMENT_0, 0, 100, "", bytes32(0), "deterministic-replay");

        address[] memory matching = new address[](1);
        matching[0] = address(validator);
        (uint64 c1,) = registry.getSummary(AGENT_ID, matching, "");
        assertEq(c1, 1);

        address[] memory other = new address[](1);
        other[0] = stranger;
        (uint64 c2,) = registry.getSummary(AGENT_ID, other, "");
        assertEq(c2, 0);
    }

    function test_Summary_FiltersByTag() public {
        _request();
        vm.prank(operator);
        validator.publishVerdict(COMMITMENT_0, 0, 100, "", bytes32(0), "deterministic-replay");

        (uint64 hit,) = registry.getSummary(AGENT_ID, new address[](0), "deterministic-replay");
        assertEq(hit, 1);

        (uint64 miss,) = registry.getSummary(AGENT_ID, new address[](0), "tee-attestation");
        assertEq(miss, 0);
    }

    // ------------------------------------------------------------------
    // Fuzz
    // ------------------------------------------------------------------

    /// @notice The average of valid responses can never exceed 100, which is
    ///         what makes the uint8 downcast in getSummary safe.
    function testFuzz_SummaryAverage_NeverExceeds100(uint8 a, uint8 b, uint8 c) public {
        a = uint8(bound(a, 0, 100));
        b = uint8(bound(b, 0, 100));
        c = uint8(bound(c, 0, 100));

        uint8[3] memory responses = [a, b, c];

        for (uint256 i = 0; i < 3; i++) {
            bytes32 h = keccak256(abi.encode("fuzz", i));
            vm.prank(AGENT_OWNER);
            registry.validationRequest(address(validator), AGENT_ID, "", h);
            vm.prank(address(validator));
            registry.validationResponse(h, responses[i], "", bytes32(0), "");
        }

        (uint64 count, uint8 avg) = registry.getSummary(AGENT_ID, new address[](0), "");
        assertEq(count, 3);
        assertLe(avg, 100);
    }

    /// @notice Only the owner or an approved operator may request validation,
    ///         for any address the fuzzer picks.
    function testFuzz_OnlyAuthorizedCanRequest(address caller) public {
        vm.assume(caller != AGENT_OWNER);
        vm.assume(!IIdentityRegistry(IDENTITY_REGISTRY).isAuthorizedOrOwner(caller, AGENT_ID));

        vm.prank(caller);
        vm.expectRevert();
        registry.validationRequest(address(validator), AGENT_ID, "", keccak256(abi.encode(caller)));
    }

    // ------------------------------------------------------------------

    function _request() private {
        vm.prank(AGENT_OWNER);
        registry.validationRequest(address(validator), AGENT_ID, "ipfs://request", COMMITMENT_0);
    }
}
