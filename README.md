# ChainProof

A verifiable AI trading agent. Every trading decision is committed on-chain as a hash of its full input snapshot, so anyone can check that the published record matches what was actually recorded — without trusting me.

Registered as an ERC-8004 agent on Ethereum Sepolia, **agentId 9896**.

---

## Check it yourself

```bash
git clone https://github.com/Zenish2001/ChainProof.git
cd ChainProof/verification-layer
pip install -r requirements.txt
python verify.py
```

Takes about ten seconds. No keys, no configuration, no accounts. It reads the 30 published trading decisions from this repository, recomputes each commitment hash, pulls the corresponding records from Ethereum Sepolia, and compares them.

```
RESULT: 30/30 commitments verified
```

Change a single price in `results/chainproof_replay_decisions.csv` and re-run it. That decision fails. The on-chain record cannot be changed at all.

---

## The problem

AI trading bots make claims about strategy, risk controls and past performance that nobody outside can verify. An operator can report a cherry-picked backtest, quietly change the risk rules after showing a track record, or misstate whether a live trade followed the declared logic. The decision process runs privately, so trust rests on the operator's word.

ChainProof narrows that gap for one specific bot: mine.

---

## How it works

**The bot.** Seven technical indicators, a 4-of-7 majority vote, risk-managed execution with stop-loss and take-profit. Lives in [`trading-bot/`](trading-bot/).

**The commitment.** Each decision's full input snapshot — price, every indicator value, the decision itself, and the active risk parameters — is serialised canonically and hashed with keccak256. Binding the risk parameters into the hash means a commitment is tied to a specific rule-set, not just to a price.

**The record.** Each hash is submitted to [`ChainProofRegistry`](https://sepolia.etherscan.io/address/0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955) on Ethereum Sepolia. Thirty individually confirmed transactions.

**The check.** `verify.py` rebuilds every hash from the published data and compares against the chain.

---

## ERC-8004

ChainProof is registered under [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004), the draft standard for trustless agent identity, and publishes its verification results through a Validation Registry.

| | |
|---|---|
| agentId | 9896 |
| Identity Registry | [`0x8004A818…BD9e`](https://sepolia.etherscan.io/address/0x8004A818BFB912233c491871b3d84c89A494BD9e) (canonical) |
| ValidationRegistry | [`0xC640b92b…0d77`](https://sepolia.etherscan.io/address/0xC640b92bAe5C832c8C8787F4F0fB894EF3De0d77) |
| ChainProofValidator | [`0xf3eF4e50…5856`](https://sepolia.etherscan.io/address/0xf3eF4e50A01d6ec110A231BF2C57E6aE8E625856) |

Full addresses, transaction hashes and gas figures in [DEPLOYMENTS.md](DEPLOYMENTS.md).

Two things came up building this that are worth stating plainly.

**No Validation Registry is deployed on any chain.** The canonical contracts repository lists Identity and Reputation addresses for more than twenty networks and no Validation Registry addresses; the official deployments were removed in PR #11. So there was no on-chain venue to publish a validation result into, and this project deploys one.

**The spec states an authorization rule without specifying how to enforce it.** `ERC8004SPEC.md` requires `validationRequest` to be called by the owner or operator of an agentId, but never names the Identity Registry function that checks it — `ownerOf`, `isAuthorizedOrOwner` and `getApproved` appear nowhere in the document, and no interface is declared for cross-contract calls. The CC0 reference implementation resolved this by calling `agentExists()`, which the canonical registry does not expose, so it reverts against the live deployment. This implementation uses `isAuthorizedOrOwner`, and there is a fork test asserting both halves of that against real Sepolia state.

```bash
cd validator
forge test --fork-url https://ethereum-sepolia-rpc.publicnode.com
```

19 tests, including fuzz runs, against the live registries rather than mocks.

---

## What this proves, and what it doesn't

**It proves** the on-chain commitments and the published decision data are the same object. Any edit to the published data breaks the hash; the chain record cannot be edited.

**It does not prove the strategy is good.** The verification is about record integrity, not profitability.

**It does not prove the parameters were chosen honestly.** `position_size=0.95, stop_loss=0.03, take_profit=0.20` are described as the winning row from a comparison sweep. The commitments show those parameters produce those decisions. They do not show the parameters were not selected after seeing the results.

**It is backtest replay, not live trading.** The committed set is the entry and exit legs of closed trades from a historical backtest, truncated to the first 30 decisions. Hold decisions are not committed.

**Re-running the strategy from raw prices is not currently reproducible.** `verify.py` checks the commitments against the published decision data. It does not re-fetch market prices and re-run the indicators, because the price database used for the original run is not part of this repository. That is a real gap, and closing it means committing the price series as a fixture — see below.

**Hashes prove records were not rewritten, never that none are missing.** This is a general property of commitment schemes and it applies to ERC-8004's reputation and validation registries too. An operator who commits only favourable decisions produces a fully verifiable and still misleading record. What makes omission detectable here is that the replay is deterministic over a declared parameter set, so an independent party can derive the complete expected decision sequence and compare — not anything the verifier does by itself.

---

## Repository layout

```
ChainProof/
├── verification-layer/   verify.py, commitment pipeline, ChainProofRegistry
├── validator/            ERC-8004 ValidationRegistry + ChainProofValidator (Foundry)
├── trading-bot/          the strategy engine, backtester, dashboard
└── agent.json            ERC-8004 registration file
```

## Next

- Commit the price series as a fixture so the strategy re-run is reproducible from a clean clone.
- Commit hold decisions, not only executed trades, so the committed set is complete by construction rather than by argument.
- Publish the replay report and set `responseHash` on the validation response, which is currently zero.

## License

MIT — see [LICENSE](LICENSE).

**Zenish Borad** · [LinkedIn](https://www.linkedin.com/in/zenish-borad) · [GitHub](https://github.com/Zenish2001) · zenish42@gmail.com
