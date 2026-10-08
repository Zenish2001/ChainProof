/*
 * ChainProof dashboard.
 *
 * Verification happens here, in the visitor's browser:
 *   1. keccak256 over each decision's canonical JSON (the published data),
 *   2. the stored commitment read from ChainProofRegistry on Sepolia,
 *   3. the signer recovered from the stored EIP-191 signature.
 * The server only supplies the published decisions. It never supplies a
 * hash or a verdict.
 */
(function () {
  "use strict";

  const EXPLORER = "https://sepolia.etherscan.io";
  const REGISTRY_ABI = [
    "function getCommitmentCount() view returns (uint256)",
    "function getCommitment(uint256 index) view returns (bytes32 commitmentHash, string action, uint256 timestamp, address signer, bytes signature)",
  ];
  const VALIDATION_ABI = [
    "function getValidationStatus(bytes32 requestHash) view returns (address validatorAddress, uint256 agentId, uint8 response, bytes32 responseHash, string tag, uint256 lastUpdate)",
    "function getSummary(uint256 agentId, address[] validatorAddresses, string tag) view returns (uint64 count, uint8 averageResponse)",
  ];
  const SIGNALS = ["BUY", "SELL", "HOLD"];
  const VISIBLE_ROWS = 10;
  const ACTIONS = ["BUY", "SELL", "STOP_LOSS", "TAKE_PROFIT", "SIGNAL"];

  const $ = (id) => document.getElementById(id);
  const { pyJson } = window.ChainProofCanonical;

  let DATA = null;
  const onchain = {}; // index -> { hash, signer, signature }
  const results = {}; // index -> { hashOk, signerOk, recomputed, recovered }
  const openRows = new Set();
  let providerPromise = null;
  let rpcHost = "";

  // ------------------------------------------------------------- helpers
  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  const short = (h, n = 6) => (h ? `${h.slice(0, n + 2)}…${h.slice(-4)}` : "");
  const usd = (n) => "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  function fmtDate(ts) {
    const d = new Date(String(ts).replace(" ", "T"));
    if (Number.isNaN(d.getTime())) return String(ts);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }
  const ACTION_LABEL = { BUY: "Buy", SELL: "Sell", STOP_LOSS: "Stop-loss", TAKE_PROFIT: "Take-profit", SIGNAL: "Exit on signal" };
  const actionLabel = (a) => ACTION_LABEL[a] || a;
  const hashOf = (text) => ethers.keccak256(ethers.toUtf8Bytes(text));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function retry(fn, tries = 4) {
    let last;
    for (let i = 0; i < tries; i++) {
      try {
        return await fn();
      } catch (err) {
        last = err;
        await sleep(500 * 2 ** i);
      }
    }
    throw last;
  }

  // ------------------------------------------------------------ provider
  function getProvider() {
    if (!providerPromise) {
      providerPromise = (async () => {
        const net = ethers.Network.from(DATA.chain_id);
        for (const url of DATA.rpc_urls) {
          try {
            const p = new ethers.JsonRpcProvider(url, net, { staticNetwork: net, batchMaxCount: 1 });
            await p.getBlockNumber();
            rpcHost = new URL(url).host;
            return p;
          } catch {
            /* try the next one */
          }
        }
        providerPromise = null;
        throw new Error("Couldn't reach the Sepolia network. Check your connection and try again.");
      })();
    }
    return providerPromise;
  }

  async function registry() {
    return new ethers.Contract(DATA.contract, REGISTRY_ABI, await getProvider());
  }

  async function fetchCommitment(i) {
    if (onchain[i]) return onchain[i];
    const c = await registry();
    const r = await retry(() => c.getCommitment(i));
    onchain[i] = { hash: String(r[0]).toLowerCase(), signer: r[3], signature: r[4] };
    return onchain[i];
  }

  // -------------------------------------------------------- verification
  async function checkOne(i) {
    const d = DATA.decisions[i];
    const oc = await fetchCommitment(i);
    const recomputed = hashOf(d.canonical).toLowerCase();
    const hashOk = recomputed === oc.hash;
    let recovered = null;
    try {
      recovered = ethers.verifyMessage(ethers.getBytes(oc.hash), oc.signature);
    } catch {
      recovered = null;
    }
    const a = DATA.attester.toLowerCase();
    const signerOk = Boolean(recovered) && recovered.toLowerCase() === a && String(oc.signer).toLowerCase() === a;
    results[i] = { hashOk, signerOk, recomputed, recovered };
    renderRow(i);
  }

  async function verifyAll() {
    const btn = $("verify-btn");
    btn.disabled = true;
    btn.textContent = "Verifying…";
    $("verify-progress").hidden = false;
    $("verify-result").innerHTML = "";
    try {
      const c = await registry();
      const count = Number(await retry(() => c.getCommitmentCount()));
      const n = Math.min(count, DATA.decisions.length);
      let done = 0;
      const queue = [...Array(n).keys()];
      const worker = async () => {
        while (queue.length) {
          const i = queue.shift();
          const chip = $(`chip-${i}`);
          if (chip) chip.className = "chip chip-checking";
          await checkOne(i);
          done++;
          $("progress-bar").style.width = `${(done / n) * 100}%`;
          $("progress-text").textContent = `Checked ${done} of ${n}`;
        }
      };
      await Promise.all([worker(), worker(), worker()]);

      const hashes = Object.values(results).filter((r) => r.hashOk).length;
      const sigs = Object.values(results).filter((r) => r.signerOk).length;
      const allGood = hashes === n && sigs === n;
      if (!allGood) $("decisions-table").classList.remove("collapsed");
      $("verify-result").innerHTML = `
        <p class="result-line ${allGood ? "good" : "bad"}">
          ${hashes} of ${n} hashes match what's stored on-chain, and ${sigs} of ${n} signatures
          are from the ChainProof key.
        </p>
        <p class="muted small">
          Your browser did the hashing and read the records from Sepolia (via ${esc(rpcHost)}).
          ${count !== DATA.decisions.length ? `The contract holds ${count} records and ${DATA.decisions.length} are published here; the overlap was compared.` : ""}
        </p>`;
      btn.textContent = "Verify again";
    } catch (err) {
      console.error(err);
      $("verify-result").innerHTML = `<p class="result-line bad">${esc(err.message || "Verification failed.")}</p>`;
      btn.textContent = "Try again";
    } finally {
      btn.disabled = false;
      $("verify-progress").hidden = true;
      if (openRows.size) openRows.forEach(renderDetail);
      updateTamper();
    }
  }

  // --------------------------------------------------------------- table
  function statusCell(i) {
    const r = results[i];
    if (!r) return `<span class="status status-pending">Not checked</span>`;
    if (r.hashOk && r.signerOk) return `<span class="status status-good">Verified</span>`;
    if (!r.hashOk) return `<span class="status status-bad">Hash differs</span>`;
    return `<span class="status status-bad">Bad signature</span>`;
  }

  function renderTable() {
    $("decision-rows").innerHTML = DATA.decisions
      .map((d) => {
        const p = d.payload;
        return `
        <tr id="row-${d.index}" class="decision-row${d.index >= VISIBLE_ROWS ? " extra" : ""}">
          <td class="mono">${d.index}</td>
          <td>${esc(fmtDate(p.timestamp))}</td>
          <td><span class="role role-${p.role === "ENTRY" ? "entry" : "exit"}">${p.role === "ENTRY" ? "Entry" : "Exit"}</span> ${esc(actionLabel(p.action))}</td>
          <td class="num">${usd(p.price)}</td>
          <td id="status-${d.index}">${statusCell(d.index)}</td>
          <td>${d.tx_hash ? `<a class="tx-link" href="${EXPLORER}/tx/${esc(d.tx_hash)}" target="_blank" rel="noreferrer">${esc(short(d.tx_hash, 4))}</a>` : "–"}</td>
          <td class="num"><button class="link-button" aria-expanded="false" aria-controls="detail-${d.index}" data-toggle="${d.index}">Details</button></td>
        </tr>
        <tr id="detail-${d.index}" class="detail-row${d.index >= VISIBLE_ROWS ? " extra" : ""}" hidden><td colspan="7"></td></tr>`;
      })
      .join("");
    const toggle = $("rows-toggle");
    if (DATA.decisions.length > VISIBLE_ROWS) {
      toggle.hidden = false;
      toggle.textContent = `Show all ${DATA.decisions.length} decisions`;
      toggle.addEventListener("click", () => {
        const collapsed = $("decisions-table").classList.toggle("collapsed");
        toggle.textContent = collapsed ? `Show all ${DATA.decisions.length} decisions` : `Show the first ${VISIBLE_ROWS} only`;
      });
    }
    $("decision-rows").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-toggle]");
      if (!btn) return;
      const i = Number(btn.dataset.toggle);
      const row = $(`detail-${i}`);
      const open = row.hidden;
      row.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Hide" : "Details";
      if (open) {
        openRows.add(i);
        renderDetail(i);
      } else {
        openRows.delete(i);
      }
    });
  }

  function renderLedger() {
    $("ledger").innerHTML = DATA.decisions
      .map((d) => {
        const h = hashOf(d.canonical).toLowerCase();
        return `<li id="chip-${d.index}" class="chip chip-wait" title="#${d.index} ${esc(actionLabel(d.payload.action))}, hash ${h.slice(0, 10)}…">${d.index}</li>`;
      })
      .join("");
  }

  function renderRow(i) {
    const cell = $(`status-${i}`);
    if (cell) cell.innerHTML = statusCell(i);
    const chip = $(`chip-${i}`);
    const r = results[i];
    if (chip && r) chip.className = `chip ${r.hashOk && r.signerOk ? "chip-ok" : "chip-bad"}`;
    if (openRows.has(i)) renderDetail(i);
  }

  function renderDetail(i) {
    const d = DATA.decisions[i];
    const oc = onchain[i];
    const r = results[i];
    const recomputed = hashOf(d.canonical).toLowerCase();
    const match = oc ? recomputed === oc.hash : null;
    $(`detail-${i}`).firstElementChild.innerHTML = `
      <div class="detail">
        <div class="detail-col">
          <h4>What was hashed</h4>
          <pre class="payload">${esc(JSON.stringify(d.payload, null, 2))}</pre>
          <details>
            <summary>Exact bytes (sorted keys, no spaces)</summary>
            <code class="canonical">${esc(d.canonical)}</code>
          </details>
        </div>
        <div class="detail-col">
          <h4>The check</h4>
          <dl class="proof">
            <dt>keccak256 of those bytes, computed in your browser</dt>
            <dd><code class="hash">${recomputed}</code></dd>
            <dt>Hash stored on Sepolia</dt>
            <dd>${oc ? `<code class="hash">${oc.hash}</code>` : `<span class="muted">Press “Verify” above to read it from the chain.</span>`}</dd>
            ${match === null ? "" : `<dd class="${match ? "good" : "bad"}">${match ? "Same" : "Different"}</dd>`}
            <dt>Signed by</dt>
            <dd>${
              r && r.recovered
                ? `<code class="hash">${r.recovered}</code> ${r.signerOk ? '<span class="good">(the ChainProof key)</span>' : '<span class="bad">(not the ChainProof key)</span>'}`
                : `<span class="muted">Recovered after verification.</span>`
            }</dd>
            <dt>Recorded in</dt>
            <dd>${
              d.tx_hash
                ? `<a href="${EXPLORER}/tx/${esc(d.tx_hash)}" target="_blank" rel="noreferrer">transaction ${esc(short(d.tx_hash))}</a>${d.block_number ? `, block ${d.block_number.toLocaleString("en-US")}` : ""}`
                : "–"
            }</dd>
          </dl>
        </div>
      </div>`;
  }

  // --------------------------------------------------------- price chart
  function renderChart() {
    const ds = DATA.decisions;
    const W = 960, H = 260, M = { t: 16, r: 16, b: 34, l: 72 };
    const PW = W - M.l - M.r, PH = H - M.t - M.b;
    const prices = ds.map((d) => d.payload.price);
    let lo = Math.min(...prices), hi = Math.max(...prices);
    const pad = (hi - lo) * 0.1 || 1;
    lo -= pad;
    hi += pad;
    const x = (i) => M.l + (ds.length === 1 ? PW / 2 : (i / (ds.length - 1)) * PW);
    const y = (v) => M.t + PH - ((v - lo) / (hi - lo)) * PH;
    const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
    const line = ds.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.payload.price).toFixed(1)}`).join("");
    const dots = ds
      .map(
        (d, i) => `<circle class="${d.payload.role === "ENTRY" ? "pt-entry" : "pt-exit"}" cx="${x(i).toFixed(1)}" cy="${y(d.payload.price).toFixed(1)}" r="4.5">
          <title>#${i} ${actionLabel(d.payload.action)} at ${usd(d.payload.price)} on ${fmtDate(d.payload.timestamp)}</title></circle>`
      )
      .join("");
    const first = fmtDate(ds[0].payload.timestamp), last = fmtDate(ds[ds.length - 1].payload.timestamp);
    $("price-chart").innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="BTC-USD price at each of the ${ds.length} decisions, ${first} to ${last}.">
        ${ticks
          .map(
            (t) => `<line class="grid" x1="${M.l}" x2="${M.l + PW}" y1="${y(t)}" y2="${y(t)}"/>
                    <text class="tick" x="${M.l - 10}" y="${y(t) + 4}" text-anchor="end">${"$" + Math.round(t / 1000) + "k"}</text>`
          )
          .join("")}
        <line class="axis" x1="${M.l}" x2="${M.l + PW}" y1="${M.t + PH}" y2="${M.t + PH}"/>
        <text class="tick" x="${M.l}" y="${H - 8}">${esc(first)}</text>
        <text class="tick" x="${M.l + PW}" y="${H - 8}" text-anchor="end">${esc(last)}</text>
        <path class="price-line" d="${line}"/>
        ${dots}
      </svg>`;
  }

  // ---------------------------------------------------------- tamper lab
  const tamper = { index: 0, edited: null };

  function fieldDefs(p) {
    const defs = [
      { key: "price", label: "BTC price", kind: "number", get: (o) => o.price, set: (o, v) => (o.price = v) },
      { key: "action", label: "Decision", kind: "select", options: ACTIONS, get: (o) => o.action, set: (o, v) => (o.action = v) },
      { key: "signal_strength", label: "Signal strength", kind: "number", get: (o) => o.signal_strength, set: (o, v) => (o.signal_strength = v) },
      { key: "overall_signal", label: "Overall signal", kind: "select", options: SIGNALS, get: (o) => o.overall_signal, set: (o, v) => (o.overall_signal = v) },
    ];
    const indLabel = { ind_rsi_signal: "RSI vote", ind_macd_signal: "MACD vote", ind_ma_signal: "SMA 20/50 vote", ind_bb_signal: "Bollinger vote" };
    Object.keys(p.indicators || {}).sort().forEach((k) => {
      defs.push({
        key: k,
        label: indLabel[k] || k,
        kind: typeof p.indicators[k] === "number" ? "number" : "select",
        options: SIGNALS,
        get: (o) => o.indicators[k],
        set: (o, v) => (o.indicators[k] = v),
      });
    });
    [["stop_loss", "Stop-loss"], ["take_profit", "Take-profit"], ["position_size", "Position size"]].forEach(([k, label]) => {
      defs.push({ key: k, label, kind: "number", get: (o) => o.risk_params[k], set: (o, v) => (o.risk_params[k] = v) });
    });
    return defs;
  }

  function setupTamper() {
    $("tamper-pick").innerHTML = DATA.decisions
      .map((d) => `<option value="${d.index}">#${d.index} ${esc(actionLabel(d.payload.action))}, ${esc(fmtDate(d.payload.timestamp))}</option>`)
      .join("");
    $("tamper-pick").addEventListener("change", (e) => loadTamper(Number(e.target.value)));
    $("tamper-reset").addEventListener("click", () => loadTamper(tamper.index));
    $("tamper-fields").addEventListener("input", onTamperInput);
    loadTamper(0);
  }

  function loadTamper(i) {
    tamper.index = i;
    const d = DATA.decisions[i];
    tamper.edited = JSON.parse(JSON.stringify(d.payload));
    const defs = fieldDefs(d.payload);
    $("tamper-fields").innerHTML = defs
      .map((f) => {
        const v = f.get(d.payload);
        const input =
          f.kind === "select"
            ? `<select data-key="${f.key}">${[...new Set([...(f.options || []), v])]
                .map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`)
                .join("")}</select>`
            : `<input data-key="${f.key}" inputmode="decimal" value="${esc(v)}" />`;
        return `<label class="field"><span class="field-label">${esc(f.label)}</span>${input}</label>`;
      })
      .join("");

    // The serializer must reproduce the published bytes before edits mean anything.
    const faithful = pyJson(d.payload) === d.canonical;
    $("tamper-note").textContent = faithful
      ? "Hashes update as you type. Nothing you do here touches the chain."
      : "This decision contains a value the in-browser serializer can't reproduce exactly, so editing is turned off for it.";
    $("tamper-fields").querySelectorAll("input,select").forEach((el) => (el.disabled = !faithful));

    $("tamper-onchain").textContent = onchain[i] ? onchain[i].hash : "Reading from Sepolia…";
    if (!onchain[i]) {
      fetchCommitment(i)
        .then(() => tamper.index === i && updateTamper())
        .catch(() => {
          if (tamper.index === i) $("tamper-onchain").textContent = "Couldn't reach Sepolia. Try again in a moment.";
        });
    }
    updateTamper();
  }

  function onTamperInput(e) {
    const el = e.target;
    const key = el.dataset.key;
    if (!key) return;
    const d = DATA.decisions[tamper.index];
    const f = fieldDefs(d.payload).find((x) => x.key === key);
    if (f.kind === "number") {
      const n = Number(el.value.trim());
      const valid = el.value.trim() !== "" && Number.isFinite(n);
      el.classList.toggle("invalid", !valid);
      if (!valid) return;
      f.set(tamper.edited, n);
    } else {
      f.set(tamper.edited, el.value);
    }
    updateTamper();
  }

  function updateTamper() {
    if (!DATA || !tamper.edited) return;
    const i = tamper.index;
    const d = DATA.decisions[i];
    const editedHash = hashOf(pyJson(tamper.edited)).toLowerCase();
    $("tamper-edited").textContent = editedHash;
    const oc = onchain[i];
    if (oc) $("tamper-onchain").textContent = oc.hash;

    const changed = fieldDefs(d.payload)
      .filter((f) => f.get(d.payload) !== f.get(tamper.edited))
      .map((f) => f.label);
    $("tamper-fields").querySelectorAll("[data-key]").forEach((el) => {
      const f = fieldDefs(d.payload).find((x) => x.key === el.dataset.key);
      el.closest(".field").classList.toggle("changed", f.get(d.payload) !== f.get(tamper.edited));
    });

    const verdict = $("tamper-verdict");
    if (!oc) {
      verdict.className = "verdict";
      verdict.textContent = "";
      return;
    }
    if (editedHash === oc.hash) {
      verdict.className = "verdict good";
      verdict.textContent = changed.length
        ? "Matches the stored hash again."
        : "Matches the stored hash. This is the decision as it was recorded.";
    } else {
      verdict.className = "verdict bad";
      const list = changed.length > 1 ? `${changed.slice(0, -1).join(", ")} and ${changed[changed.length - 1]}` : changed[0];
      verdict.textContent = `Doesn't match. You changed ${list}, and the stored record can't be changed, so the edit shows up.`;
    }
  }

  // --------------------------------------------------------- performance
  function renderPerformance() {
    $("perf-rows").innerHTML = DATA.performance
      .map(
        (p) => `<tr>
          <td>${esc(p.symbol)}${p.symbol === "BTC-USD" ? ' <span class="muted small">(on-chain)</span>' : ""}</td>
          <td class="num ${p.return_pct >= 0 ? "good" : "bad"}">${p.return_pct >= 0 ? "+" : "−"}${Math.abs(p.return_pct).toFixed(1)}%</td>
          <td class="num">${p.win_rate_pct.toFixed(0)}%</td>
          <td class="num">${p.sharpe.toFixed(2)}</td>
          <td class="num">${Math.round(p.stop_loss * 100)}% / ${Math.round(p.take_profit * 100)}%</td>
        </tr>`
      )
      .join("");
  }

  // -------------------------------------------------------------- ERC-8004
  async function renderErc8004() {
    const e = DATA.erc8004;
    const addr = (a) => `<a href="${EXPLORER}/address/${a}" target="_blank" rel="noreferrer"><code>${short(a)}</code></a>`;
    $("erc-facts").innerHTML = `
      <div><dt>Agent ID</dt><dd><a href="${EXPLORER}/tx/${e.registration_tx}" target="_blank" rel="noreferrer">${e.agent_id}</a></dd></div>
      <div><dt>Identity Registry (official)</dt><dd>${addr(e.identity_registry)}</dd></div>
      <div><dt>Validation Registry (mine)</dt><dd>${addr(e.validation_registry)}</dd></div>
      <div><dt>Validator (mine)</dt><dd>${addr(e.validator)}</dd></div>
      <div><dt>Agent card</dt><dd><a href="${e.agent_card}" target="_blank" rel="noreferrer">agent.json</a></dd></div>`;

    try {
      const provider = await getProvider();
      const reg = new ethers.Contract(e.validation_registry, VALIDATION_ABI, provider);
      const requestHash = hashOf(DATA.decisions[0].canonical);
      const s = await retry(() => reg.getValidationStatus(requestHash));
      const when = new Date(Number(s[5]) * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      $("erc-live").innerHTML = `
        Decision #0 has a validation record on-chain. Validator ${addr(s[0])} gave it
        <strong>${Number(s[2])} out of 100</strong> with the tag <code>${esc(s[4])}</code>, last updated ${esc(when)}.
        See the <a href="${EXPLORER}/tx/${e.request_tx}" target="_blank" rel="noreferrer">request</a> and
        <a href="${EXPLORER}/tx/${e.verdict_tx}" target="_blank" rel="noreferrer">verdict</a> transactions.
        A score of 100 means re-running the unmodified strategy reproduced the same decision. It says nothing about profit.`;
    } catch (err) {
      console.error(err);
      $("erc-live").textContent = "Couldn't read the validation record from Sepolia right now. Reload to try again.";
    }
  }

  // ----------------------------------------------------------------- init
  async function init() {
    try {
      const res = await fetch("/api/data");
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      DATA = await res.json();
    } catch (err) {
      console.error(err);
      $("decision-rows").innerHTML = `<tr><td colspan="7" class="bad">Couldn't load the published decisions. Reload the page to try again.</td></tr>`;
      return;
    }
    if (typeof ethers === "undefined") {
      $("verify-result").innerHTML = `<p class="result-line bad">The ethers.js library didn't load, so the browser can't verify. Check your connection or ad blocker and reload.</p>`;
      return;
    }
    const n = DATA.decisions.length;
    $("verify-btn").textContent = `Verify all ${n} decisions`;
    $("verify-btn").disabled = false;
    $("verify-btn").addEventListener("click", verifyAll);
    renderLedger();
    renderChart();
    renderTable();
    setupTamper();
    renderPerformance();
    renderErc8004();
  }

  init();
})();
