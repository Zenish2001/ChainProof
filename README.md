# ChainProof

[![CI](https://github.com/Zenish2001/ChainProof/actions/workflows/ci.yml/badge.svg)](https://github.com/Zenish2001/ChainProof/actions/workflows/ci.yml)

A trading bot whose every decision is recorded on Ethereum, so anyone can check it later without trusting me.

**[Live dashboard](http://18.224.206.193)** · **[Live paper-trading bot](http://18.224.206.193:8081)** · **[Contract on Etherscan](https://sepolia.etherscan.io/address/0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955)** · ERC-8004 agent **#9896**

![ChainProof dashboard](docs/dashboard.png)

## Highlights

- The bot made **30 trading decisions**. Each one was hashed (keccak256), signed (ECDSA) and stored in a contract on **Ethereum Sepolia**, where it can't be changed.
- The [dashboard](http://18.224.206.193) re-checks all 30 **in your browser**: it hashes the published data itself, reads the records from the chain and recovers the signer. Edit any decision in the tamper test and its hash stops matching.
- The agent is registered under **ERC-8004**, with a Validation Registry I wrote and deployed because the official deployments don't include one.
- **33 tests** run in CI on every push: 19 in Foundry (including fuzz tests against forked Sepolia) and 14 in Python.

## Skills shown

| Area | What this project uses |
|---|---|
| Smart contracts | Solidity, Foundry (unit, fuzz and fork tests), ERC-721 / ERC-8004, EIP-191 signatures |
| Cryptography | keccak256 commitments, ECDSA signing and signer recovery, canonical serialization |
| Backend | Python, Web3.py, eth-account, pandas, Flask |
| Frontend | JavaScript, ethers.js (verification runs in the browser) |
| Trading | Technical indicators, backtesting, risk rules (stop-loss / take-profit), Sharpe ratio |
| DevOps | GitHub Actions CI, Docker, Docker Compose, AWS EC2, Caddy |

## Requirements

| To do this | You need |
|---|---|
| Run `verify.py` or the dashboard | Python 3.10+ and an internet connection (a public Sepolia RPC is built in) |
| Run the contract tests | [Foundry](https://book.getfoundry.sh/getting-started/installation) |
| Run with Docker | Docker and Docker Compose |
| Use the dashboard | Any modern browser. No wallet or keys |

## Check it yourself

```bash
git clone https://github.com/Zenish2001/ChainProof.git
cd ChainProof/verification-layer
pip install -r requirements.txt
python verify.py
```

No keys or configuration. It takes about ten seconds:

```
RESULT: 30/30 commitment hashes verified
        30/30 signatures from the ChainProof attester
```

Change one price in `results/chainproof_replay_decisions.csv` and run it again: that decision fails. `python tamper_test.py` runs this experiment for you.

## How it works

```
Strategy decision  →  canonical JSON  →  keccak256 hash  →  ECDSA signature  →  ChainProofRegistry (Sepolia)
                                                                                       ↑
                               verify.py / dashboard: rebuild hash, read chain, recover signer
```

1. **Decide.** Four indicators vote: RSI, MACD, an SMA 20/50 crossover and Bollinger Bands. Two agreeing votes trigger a trade, with stop-loss and take-profit exits. Code in [`trading-bot/`](trading-bot/).
2. **Hash.** The price, each indicator's vote, the decision and the risk rules are written as sorted JSON and hashed with keccak256. Including the risk rules ties each record to a specific rule set, not just a price.
3. **Sign.** A dedicated key (`0xBd121B73…2c9f`) signs each hash (EIP-191), standing in for hardware-based attestation.
4. **Record.** Each hash and signature goes into [`ChainProofRegistry`](https://sepolia.etherscan.io/address/0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955): 30 confirmed transactions.
5. **Verify.** `verify.py` and the dashboard rebuild every hash from the published data, compare it with the chain and check every signature.

## ERC-8004

| | |
|---|---|
| Agent ID | 9896 |
| Identity Registry (official) | [`0x8004A818…BD9e`](https://sepolia.etherscan.io/address/0x8004A818BFB912233c491871b3d84c89A494BD9e) |
| Validation Registry (mine) | [`0xC640b92b…0d77`](https://sepolia.etherscan.io/address/0xC640b92bAe5C832c8C8787F4F0fB894EF3De0d77) |
| ChainProofValidator (mine) | [`0xf3eF4e50…5856`](https://sepolia.etherscan.io/address/0xf3eF4e50A01d6ec110A231BF2C57E6aE8E625856) |

Two findings from building this:

- **The official ERC-8004 deployments include no Validation Registry**, so I deployed my own implementation of the current spec. Its validator refuses verdicts for any decision that isn't already committed on-chain.
- **The reference Validation Registry reverts against the live Identity Registry.** It checks agents with `agentExists()`, which the deployed registry doesn't have. Mine uses `isAuthorizedOrOwner()`, and a fork test checks this against real Sepolia state.

Full addresses, transactions and gas figures are in [DEPLOYMENTS.md](DEPLOYMENTS.md).

## What this proves, and what it doesn't

**It proves** the published decisions are exactly the ones recorded on-chain, and that each was signed by the ChainProof key.

**It doesn't prove:**
- **That the strategy is good.** The committed BTC run is the best of 48 parameter sets: +38.5%, Sharpe 0.64. The same strategy returned −6.4% on ETH and −34.1% on SOL. These are in-sample numbers. [`evaluate_backtest.py`](trading-bot/evaluate_backtest.py) adds fees, a buy-and-hold benchmark and an out-of-sample test.
- **That the parameters weren't picked after seeing results.**
- **That no decisions are missing.** Hashes show records weren't rewritten, not that the set is complete. Omissions become detectable because the replay is deterministic: anyone can re-run the declared rules and compare.
- **Live trading.** The 30 committed decisions are a replay of historical data. The separate [paper-trading bot](http://18.224.206.193:8081) runs the same strategy on live prices with pretend money.

## Run it locally

| What | Commands |
|---|---|
| Verification dashboard | `cd verification-layer && pip install -r requirements.txt flask && python dashboard/dashboard_app.py` → http://localhost:5002 |
| Paper-trading bot | `cd trading-bot && pip install -r requirements-dashboard.txt && python frontend/app.py` → http://localhost:5001 |
| Contract tests | `cd validator && forge install foundry-rs/forge-std && forge test --fork-url https://ethereum-sepolia-rpc.publicnode.com` |
| Python tests | `pip install -r verification-layer/requirements.txt pytest && pytest tests/` |

Both web apps have Dockerfiles. The live versions run with Docker Compose on AWS EC2 behind a Caddy reverse proxy.

## Repository layout

```
ChainProof/
├── verification-layer/   verify.py, tamper test, commitment pipeline, dashboard
├── validator/            ERC-8004 ValidationRegistry + ChainProofValidator (Foundry)
├── trading-bot/          strategy, backtester, paper-trading bot and its dashboard
├── tests/                Python tests for the verifier and the strategy
└── agent.json            ERC-8004 registration file
```

## Next

- Commit the price-series fixture so `replay_check.py` runs from a clean clone.
- Commit hold decisions too, so the committed set is complete by construction.
- Registry v2: verify signatures on-chain with `ecrecover` and record `block.timestamp`.
- Key validation requests by `(agentId, requestHash)` to stop a third party registering a public hash first.

Contract sources are left exactly as deployed so they match the on-chain bytecode.

## License

MIT, see [LICENSE](LICENSE).

**Zenish Borad** · [LinkedIn](https://www.linkedin.com/in/zenish-borad) · [GitHub](https://github.com/Zenish2001) · borad.z@northeastern.edu
