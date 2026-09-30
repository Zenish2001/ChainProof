# ChainProof ERC-8004 — Deployment Record

Ethereum Sepolia, chainId `11155111`. All addresses verifiable at sepolia.etherscan.io.

## Identity

| | |
|---|---|
| agentId | **9896** |
| Identity Registry | `0x8004A818BFB912233c491871b3d84c89A494BD9e` (canonical, impl v2.0.0) |
| Owner | `0x7ACad346325EC88a8CC9d01C99aeAd2851fB939B` |
| agentURI | `https://raw.githubusercontent.com/Zenish2001/ChainProof/main/agent.json` |
| Registration tx | `0xb5c10780c1e8a9cfd31fffa537c763614995dd5346ad18fc3c4629394f6ea615` |
| Block | 11596426 (183,612 gas) |
| CAIP identifier | `eip155:11155111:0x8004A818BFB912233c491871b3d84c89A494BD9e#9896` |

## Validation stack

| Contract | Address | Deploy tx | Gas |
|---|---|---|---|
| ValidationRegistry | `0xC640b92bAe5C832c8C8787F4F0fB894EF3De0d77` | `0x8fbf606b2d3056bfc96b11f5578a1f639605601208ab948577fdc4502f90c82c` | 1,517,340 |
| ChainProofValidator | `0xf3eF4e50A01d6ec110A231BF2C57E6aE8E625856` | `0x366588796943b59f8ee14b8d394984620ad9ab2cb97c42b76191c0fd1fb5c1ad` | 856,240 |

Both in block 11623208. Operator: `0x7ACad346325EC88a8CC9d01C99aeAd2851fB939B`.

Supporting: ChainProofRegistry `0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955` (30 commitments).

## First validation cycle

Block 11623216.

| Step | Tx | Gas |
|---|---|---|
| `validationRequest` | `0x66f3b6544d768c25a0cd9baf98bfec13e3f8556bdce18368ccf1865d34c6e64d` | 219,524 |
| `publishVerdict` | `0x4cc7b8e25495112ed845fa82dc7215394e38ebeb4f7a887188f438cf5739504f` | 127,832 |

`requestHash` `0x6c87efc43ec1281875205c284b67657bc6db5d81c6e746eb146a7766d1586305` — commitment #0, a BUY at unix 1712966400.

`getValidationStatus` returns: validator `0xf3eF4e50…`, agentId 9896, response 100, tag `deterministic-replay`, lastUpdate 1788396960.
`getSummary(9896, [], "")` returns count 1, averageResponse 100.

## What the deployment demonstrates

**A Validation Registry for ChainProof now exists.** The canonical contracts repo lists Identity and Reputation addresses for 20+ networks and zero Validation Registry addresses; PR #11 removed the official deployments while the Validation Registry is reworked. Without an official registry, ChainProof's `supportedTrust` claim had no on-chain venue to resolve against, so this deployment provides one.

**The authorization gap is real and the fix works.** ERC8004SPEC.md requires `validationRequest` to be called by the owner or operator of `agentId` but never specifies the Identity Registry interface that enforces it — no `ownerOf`, no `isAuthorizedOrOwner`, no `IIdentityRegistry` declaration anywhere in the document. The CC0 reference implementation resolved this with `agentExists()`, absent from the canonical registry's ABI, so it reverts in production. This deployment uses `isAuthorizedOrOwner(address,uint256)`, and tx `0x66f3b654…` is that call succeeding against the live registry.

**Verdicts are bound to commitments.** Under the bare spec a validator is an address posting an integer against an arbitrary hash. `publishVerdict` reverts unless the `requestHash` matches a commitment already stored in ChainProofRegistry, which works because the spec's `requestHash` and ChainProof's `commitmentHash` are both keccak256 over the same decision payload.

## Scope limits

The replay itself is off-chain and necessarily so. Response 100 means: this commitment exists on-chain, and an off-chain replay of the unmodified strategy under the declared parameters reproduced it. It does not mean the strategy is profitable, that the parameters were not selected post-hoc, or that the committed set is complete — the last being a general property of ERC-8004, where hashes prove records were not rewritten but never that none are missing.

The registry is deliberately non-upgradeable, unlike the canonical registries, which are UUPS proxies owned on both mainnet and Sepolia by a single externally-owned account with no multisig or timelock. The spec text never mentions upgradeability or upgrade authority.
