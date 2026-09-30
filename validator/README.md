# validator — ERC-8004 Validation Registry and ChainProof validator

Foundry project containing ChainProof's ERC-8004 contracts, deployed on Ethereum Sepolia (addresses and transaction hashes in [DEPLOYMENTS.md](../DEPLOYMENTS.md)).

| Contract | What it does |
|---|---|
| [`ValidationRegistry.sol`](src/ValidationRegistry.sol) | An implementation of the ERC-8004 Validation Registry, since the official deployments include none. Non-upgradeable, checks agent authorization through the canonical Identity Registry's `isAuthorizedOrOwner`, and rejects duplicate `requestHash`es so one agent cannot overwrite another's pending request. |
| [`ChainProofValidator.sol`](src/ChainProofValidator.sol) | The validator that publishes ChainProof's verdicts. A verdict can only be published for a `requestHash` that exists as a commitment in `ChainProofRegistry`, so a result about an uncommitted decision cannot be expressed. |
| [`IERC8004.sol`](src/IERC8004.sol) | Interfaces for the Identity Registry, Validation Registry and ChainProofRegistry. |

The design decisions and the spec ambiguities they resolve are documented in the NatSpec at the top of each contract.

## Tests

19 tests, including 2 fuzz tests, run against a fork of live Sepolia — the real canonical Identity Registry and the real ChainProofRegistry, not mocks. Two of them pin the central finding: the canonical registry does not expose `agentExists()`, which the reference implementation calls, and does expose `isAuthorizedOrOwner`, which this implementation uses.

```bash
cd validator
forge install foundry-rs/forge-std   # lib/ is not committed
forge test --fork-url https://ethereum-sepolia-rpc.publicnode.com -vv
```

## Scripts

`script/Deploy.s.sol` deploys the ValidationRegistry and ChainProofValidator. `script/RequestAndPublish.s.sol` files a validation request for commitment #0 and publishes the verdict; it reads the deployed addresses from the `VALIDATION_REGISTRY` and `VALIDATOR` environment variables. Broadcast records for both Sepolia runs are in `broadcast/`.
