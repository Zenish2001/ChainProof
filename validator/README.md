# ERC-8004 Validator

The Foundry project with ChainProof's ERC-8004 contracts: a Validation Registry and the validator that publishes ChainProof's results, both deployed on Ethereum Sepolia.

**[ValidationRegistry on Etherscan](https://sepolia.etherscan.io/address/0xC640b92bAe5C832c8C8787F4F0fB894EF3De0d77)** · **[ChainProofValidator on Etherscan](https://sepolia.etherscan.io/address/0xf3eF4e50A01d6ec110A231BF2C57E6aE8E625856)** · all addresses and transactions in [DEPLOYMENTS.md](../DEPLOYMENTS.md)

## Highlights

- **A Validation Registry where none existed.** The official ERC-8004 deployments include no Validation Registry, so this is an implementation of the current spec. It's non-upgradeable and rejects duplicate request hashes, so one agent can't overwrite another's pending request.
- **Verdicts are tied to on-chain records.** `ChainProofValidator` only publishes a result for a hash that already exists as a commitment in `ChainProofRegistry`. A verdict about a decision that was never committed can't be expressed.
- **Found a bug in the reference implementation.** It checks agents with `agentExists()`, which the live Identity Registry doesn't have, so it reverts in production. This registry uses `isAuthorizedOrOwner()`, which the live registry supports.
- **19 tests against real Sepolia state**, including 2 fuzz tests. They run on a fork of the live network with the real Identity Registry and ChainProofRegistry, not mocks. Two of them pin the finding above.

## Requirements

- [Foundry](https://book.getfoundry.sh/getting-started/installation) (`forge`)
- Internet access for the Sepolia fork (a free public RPC works)
- To deploy: a funded Sepolia key in your environment

## Run the tests

```bash
cd validator
forge install foundry-rs/forge-std      # lib/ is not committed
forge test --fork-url https://ethereum-sepolia-rpc.publicnode.com -vv
```

## Deploy

```bash
# deploy ValidationRegistry and ChainProofValidator
forge script script/Deploy.s.sol --rpc-url $SEPOLIA_RPC_URL --broadcast

# file a validation request for commitment #0 and publish the verdict
export VALIDATION_REGISTRY=0x... VALIDATOR=0x...
forge script script/RequestAndPublish.s.sol --rpc-url $SEPOLIA_RPC_URL --broadcast
```

Broadcast records for both Sepolia runs are in `broadcast/`.

## Files

| Path | Purpose |
|---|---|
| `src/ValidationRegistry.sol` | ERC-8004 Validation Registry: requests, responses, per-agent summaries |
| `src/ChainProofValidator.sol` | Publishes ChainProof verdicts, only for committed decisions |
| `src/IERC8004.sol` | Interfaces for the Identity, Validation and ChainProof registries |
| `test/ValidationRegistry.t.sol` | Unit, fuzz and fork tests |
| `script/` | Deployment and request/publish scripts |

The design decisions and the spec gaps they resolve are explained in the NatSpec at the top of each contract. Sources are left exactly as deployed so they match the verified bytecode.

## Skills shown

Solidity · Foundry (unit, fuzz and fork tests, scripts) · ERC-8004 · ERC-721 · cross-contract calls · reading and implementing a draft standard
