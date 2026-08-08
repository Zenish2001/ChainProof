<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:232526,100:414345&height=200&section=header&text=ChainProof&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=A%20Verifiable%20AI%20Trading%20Agent&descAlignY=55&descSize=20" width="100%"/>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&pause=1000&color=8E8E8E&center=true&vCenter=true&width=600&lines=Trading+decisions+that+aren't+just+executed...;They're+provable.;On-chain+verification+for+AI+trading+agents." alt="Typing SVG" />

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Solidity](https://img.shields.io/badge/Solidity-Testnet-363636?style=for-the-badge&logo=solidity&logoColor=white)]()
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=for-the-badge)]()

</div>

<br/>

An automated cryptocurrency trading system extended with an **on-chain verification layer** — so trading decisions aren't just executed, they're **provable**. Every trade is committed on-chain in a form that lets an independent party recompute the signal logic from public market data and confirm the on-chain record matches what the declared strategy should have produced.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## 🧩 The Problem

AI-driven trading bots make claims about their strategy, risk controls, and historical performance that a user has no independent way to verify. An operator could report a cherry-picked backtest, quietly change risk rules after showing a track record, or misstate whether a live trade matched the declared logic. Because the decision process runs privately, trust rests on the operator's word rather than on anything provable.

**ChainProof closes that gap** — every trading decision is committed on-chain in a form anyone can independently recompute and check.

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## ⚙️ How It Works

**1. Trading Bot generates a signal**
7 technical indicators → 4-of-7 majority vote → buy/sell/hold decision → risk-managed execution

**2. Commit** — the trade's inputs, indicator values, and decision are hashed into a single commitment

**3. Log** — the commitment is submitted to a smart contract on a public testnet, which emits an event

**4. Verify** — an independent script pulls the same historical price data, re-runs the exact strategy code from this repo, recomputes the commitment, and checks it against the on-chain record

Any mismatch — a tampered trade, a quietly changed rule, a misreported result — gets flagged automatically, since the verifier is working from the same public data and open-source logic anyone else could run.

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## 📊 Highlights

<div align="center">

| Metric | Value |
|:---|:---:|
| 💰 Backtested Return (BTC-USD) | **+40.38%** |
| 📈 Sharpe Ratio | **0.64** |
| 📉 Max Drawdown | **-20.95%** |
| 🗃️ Historical Records Analyzed | **2,196+** |
| 🔐 Verification Layer | On-chain commitment + independent replay verifier |

</div>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## 🛠️ Tech Stack

<div align="center">

<img src="https://skillicons.dev/icons?i=python,flask,solidity,sqlite,git,html,css,js,githubactions&theme=dark" />

</div>

<br/>

**Trading engine:** Python, Flask, SQLite, Pandas/NumPy, yfinance, CCXT
**Verification layer:** Solidity, a public EVM testnet, Python (commitment hashing + verification scripts)

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## 📁 Repository Structure

```
ChainProof/
├── trading-bot/          # Full trading platform — signals, risk management,
│                          # backtesting, live dashboard (see trading-bot/README.md)
├── verification-layer/   # On-chain commitment, submission, and verification
│                          # (see verification-layer/README.md)
└── README.md              # You are here
```

- **[trading-bot/](trading-bot/)** — the trading engine: 7 technical indicators, majority-vote signal generation, risk management, paper/live trading, and a real-time dashboard.
- **[verification-layer/](verification-layer/)** — the ChainProof addition: a smart contract that logs trade commitments on a public testnet, and a verifier that independently checks the on-chain record against the strategy's actual output.

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## 🚧 Status

Actively in development. See [verification-layer/README.md](verification-layer/README.md) for current progress on the on-chain commitment and verifier components.

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:232526,100:414345&height=3&width=100%"/>

## 📄 License

MIT License — see [LICENSE](LICENSE)

<br/>

<div align="center">

## 📬 Get In Touch

<table>
<tr>
<td align="center" width="200">

<img src="https://img.icons8.com/fluency/48/user-male-circle.png" width="40"/><br/>
<b>Zenish Borad</b><br/>
<sub>Fintech & Blockchain Engineering</sub>

</td>
<td align="center" width="200">

<a href="https://www.linkedin.com/in/zenish-borad">
<img src="https://img.icons8.com/fluency/48/linkedin.png" width="40"/><br/>
<b>LinkedIn</b>
</a><br/>
<sub>zenish-borad</sub>

</td>
<td align="center" width="200">

<a href="https://github.com/Zenish2001">
<img src="https://img.icons8.com/fluency/48/github.png" width="40"/><br/>
<b>GitHub</b>
</a><br/>
<sub>@Zenish2001</sub>

</td>
<td align="center" width="200">

<a href="mailto:zenish42@gmail.com">
<img src="https://img.icons8.com/fluency/48/gmail-new.png" width="40"/><br/>
<b>Email</b>
</a><br/>
<sub>zenish42@gmail.com</sub>

</td>
</tr>
</table>

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:414345,100:232526&height=100&section=footer" width="100%"/>

</div>