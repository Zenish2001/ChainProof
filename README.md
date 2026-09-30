# ChainProof

[![CI](https://github.com/Zenish2001/ChainProof/actions/workflows/ci.yml/badge.svg)](https://github.com/Zenish2001/ChainProof/actions/workflows/ci.yml)

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

Takes about ten seconds. No keys, no configuration, no accounts. It reads the 30 published trading decisions from this repository, recomputes each commitment hash, pulls the corresponding records from Ethereum Sepolia, and compares them. It also recovers the signer of every commitment and checks it against the published ChainProof attestation address.

```
RESULT: 30/30 commitment hashes verified
        30/30 signatures from the ChainProof attester
```

Change a single price in `results/chainproof_replay_decisions.csv` and re-run it. That decision fails. The on-chain record cannot be changed at all. `python tamper_test.py` runs that experiment for you: one genuine decision, one with the price moved, and one with an indicator signal flipped.

---

## The problem

AI trading bots make claims about strategy, risk controls and past performance that nobody outside can verify. An operator can report a cherry-picked backtest, quietly change the risk rules after showing a track record, or misstate whether a live trade followed the declared logic. The decision process runs privately, so trust rests on the operator's word.

ChainProof narrows that gap for one specific bot: mine.

---

## How it works

**The bot.** Four indicators vote — RSI, MACD, an SMA 20/50 crossover and Bollinger Bands — and two agreeing signals trigger a trade (a 2–2 tie resolves to SELL). Stochastic, ATR and OBV are computed for the dashboard but do not vote. Execution is risk-managed with stop-loss and take-profit. Lives in [`trading-bot/`](trading-bot/).

**The commitment.** Each decision's input snapshot — price, signal strength, each voting indicator's BUY/SELL/HOLD signal, the decision itself, and the active risk parameters — is serialised canonically and hashed with keccak256. Binding the risk parameters into the hash means a commitment is tied to a specific rule-set, not just to a price. The commitment covers each indicator's discrete signal rather than the raw values behind it (the RSI level, the MACD line), so it binds what the vote saw, not the arithmetic that produced it.

**The signature.** Each hash is signed (EIP-191) by a dedicated attestation key, `0xBd121B73…2c9f`, standing in for TEE-based remote attestation. The registry stores the signature without checking it, so `verify.py` does: every commitment must recover to that address.

**The record.** Each hash is submitted to [`ChainProofRegistry`](https://sepolia.etherscan.io/address/0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955) on Ethereum Sepolia. Thirty individually confirmed transactions.

**The check.** `verify.py` rebuilds every hash from the published data, compares against the chain, and checks each signature.

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

**The official ERC-8004 deployments include no Validation Registry.** The canonical contracts repository lists Identity and Reputation addresses for more than twenty networks and no Validation Registry addresses; the official deployments were removed in PR #11 while the Validation Registry is reworked. So there was no official on-chain venue to publish a validation result into, and this project deploys its own implementation of the current spec. (Other teams have deployed their own Validation Registries too; this one is non-upgradeable and bound to ChainProof's commitments, as described in [`validator/`](validator/).)

**The spec states an authorization rule without specifying how to enforce it.** `ERC8004SPEC.md` requires `validationRequest` to be called by the owner or operator of an agentId, but never names the Identity Registry function that checks it — `ownerOf`, `isAuthorizedOrOwner` and `getApproved` appear nowhere in the document, and no interface is declared for cross-contract calls. The CC0 reference implementation resolved this by calling `agentExists()`, which the canonical registry does not expose, so it reverts against the live deployment. This implementation uses `isAuthorizedOrOwner`, and there is a fork test asserting both halves of that against real Sepolia state.

```bash
cd validator
forge install foundry-rs/forge-std   # lib/ is not committed
forge test --fork-url https://ethereum-sepolia-rpc.publicnode.com
```

19 tests, including fuzz runs, against the live registries rather than mocks. A further 14 Python tests in [`tests/`](tests/) cover the verifier (against the real published hashes and signatures) and the strategy (the vote rule, stop-loss and take-profit exits, and a check that the indicators never look ahead). CI runs both suites and re-verifies the chain on every push.

---

## What this proves, and what it doesn't

**It proves** the on-chain commitments and the published decision data are the same object. Any edit to the published data breaks the hash; the chain record cannot be edited.

**It does not prove the strategy is good.** The verification is about record integrity, not profitability.

**It does not prove the backtest is representative.** The committed run is the best of 48 parameter combinations on BTC-USD: +38.47% return, Sharpe 0.64, 41.7% win rate. The same strategy returned −6.40% on ETH-USD and −34.09% on SOL-USD. Those figures are in-sample and ignore trading costs. [`trading-bot/evaluate_backtest.py`](trading-bot/evaluate_backtest.py) answers the questions they leave open: the buy-and-hold return over the same period, the result after fees, and an out-of-sample test in which parameters chosen on the first 70% of the history run unchanged on the rest. The full sweep is in [`strategy_comparison.csv`](verification-layer/results/strategy_comparison.csv).

**It does not prove the parameters were chosen honestly.** `position_size=0.95, stop_loss=0.03, take_profit=0.20` are described as the winning row from a comparison sweep. The commitments show those parameters produce those decisions. They do not show the parameters were not selected after seeing the results.

**It is backtest replay, not live trading.** The committed set is the entry and exit legs of closed trades from a historical backtest, truncated to the first 30 decisions. Hold decisions are not committed.

**Re-running the strategy from raw prices needs the price fixture.** `verify.py` checks the commitments against the published decision data. `replay_check.py` goes further: it re-runs the unmodified strategy over a committed price series and checks that it reproduces all 30 committed decisions. The series is exported from the bot's database with `export_price_fixture.py` into `verification-layer/fixtures/`; until that file is committed, the replay cannot run from a clean clone.

**Hashes prove records were not rewritten, never that none are missing.** This is a general property of commitment schemes and it applies to ERC-8004's reputation and validation registries too. An operator who commits only favourable decisions produces a fully verifiable and still misleading record. What makes omission detectable here is that the replay is deterministic over a declared parameter set, so an independent party can derive the complete expected decision sequence and compare — not anything the verifier does by itself.

---

## Repository layout

```
ChainProof/
├── verification-layer/   verify.py, replay_check.py, commitment pipeline, ChainProofRegistry
├── validator/            ERC-8004 ValidationRegistry + ChainProofValidator (Foundry)
├── trading-bot/          the strategy engine, backtester, evaluate_backtest.py, dashboard
├── tests/                Python tests for the verifier and the strategy
└── agent.json            ERC-8004 registration file
```

## Next

- Commit the price series fixture so `replay_check.py` runs from a clean clone.
- Commit hold decisions, not only executed trades, so the committed set is complete by construction rather than by argument.
- Publish the replay report and set `responseHash` on the validation response, which is currently zero.
- Commit raw indicator values alongside the signals.
- Registry v2: verify signatures on-chain with `ecrecover`, restrict submissions to the attestation key, and record `block.timestamp` next to the caller-supplied market timestamp, so each commitment also proves when it landed on-chain.
- Address `requestHash` squatting in the ValidationRegistry: commitment hashes are public before `validationRequest` is called, so a party with its own agentId could register a hash first and block the rightful request. Keying requests by `(agentId, requestHash)` would remove this.

Contract sources are left exactly as deployed so they keep matching the on-chain bytecode. Two NatSpec comments predate corrections made in this README: `ChainProofValidator.sol` says the commitment covers "every indicator value" (it covers each voting indicator's signal), and `ValidationRegistry.sol` says no Validation Registry is deployed on any chain (none is in the official deployments; other teams have deployed their own).

## License

MIT — see [LICENSE](LICENSE).

**Zenish Borad** · [LinkedIn](https://www.linkedin.com/in/zenish-borad) · [GitHub](https://github.com/Zenish2001) · zenish42@gmail.com
