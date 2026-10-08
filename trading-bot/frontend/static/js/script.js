// Paper trading bot dashboard. Polls /api/state and redraws.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const usd = (n, d = 2) => (n < 0 ? "−$" : "$") + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const signedUsd = (n) => (n > 0 ? "+" : "") + usd(n);
  const pct = (n) => (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(2) + "%";
  const cls = (n) => (n > 0 ? "up" : n < 0 ? "down" : "");
  const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const timeOf = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

  const every = (sec) => {
    const m = Math.round(sec / 60);
    return m <= 1 ? "minute" : `${m} minutes`;
  };
  const prettyNote = (n) => String(n || "").replace(/Exit reason: (\w+)/, (_, r) => "Exit: " + r.toLowerCase().replace(/_/g, "-"));

  let state = null;
  let countdown = null;

  function setNum(id, text, n) {
    const el = $(id);
    el.textContent = text;
    el.className = n === undefined ? "" : cls(n);
  }

  function renderStatus() {
    const s = state;
    const el = $("status");
    el.className = "status " + (s.running ? "on" : "off");
    let text = s.running ? `Running. Checks BTC every ${every(s.check_interval)}` : "Stopped";
    if (s.running && countdown !== null) text += `, next check in ${mmss(countdown)}`;
    if (s.last_cycle) text += `. Last check at ${timeOf(s.last_cycle)}`;
    text += ".";
    if (s.last_error) text += ` Last error: ${s.last_error}`;
    $("status-text").textContent = text;
  }

  function renderAccount() {
    const a = state.account;
    setNum("acc-total", usd(a.total));
    setNum("acc-return", pct(a.return_pct), a.return_pct);
    setNum("acc-cash", usd(a.cash));
    setNum("acc-realized", signedUsd(a.realized_pnl), a.realized_pnl);
  }

  function renderPosition() {
    const r = state.rules;
    if (!state.positions.length) {
      $("position").innerHTML = `<p class="flat">No open position. The bot is in cash and waits until at least
        ${r.votes_needed} of the 4 indicators say buy.</p>
        <p class="note">When it buys, it uses ${r.position_size_pct.toFixed(0)}% of cash, with a
        ${r.stop_loss_pct.toFixed(0)}% stop-loss and a ${r.take_profit_pct.toFixed(0)}% take-profit.</p>`;
      return;
    }
    $("position").innerHTML = state.positions
      .map(
        (p) => `<dl class="pos">
          <div><dt>Holding</dt><dd>${p.quantity.toFixed(6)} ${esc(p.symbol.split("-")[0])}</dd></div>
          <div><dt>Bought at</dt><dd>${usd(p.entry_price)}</dd></div>
          <div><dt>Price now</dt><dd>${usd(p.price)}</dd></div>
          <div><dt>Unrealized</dt><dd class="${cls(p.unrealized)}">${signedUsd(p.unrealized)} (${pct(p.unrealized_pct)})</dd></div>
          <div><dt>Stop-loss at</dt><dd>${usd(p.stop_price)}</dd></div>
          <div><dt>Take-profit at</dt><dd>${usd(p.target_price)}</dd></div>
        </dl>`
      )
      .join("");
  }

  function renderSignal() {
    const sig = state.signals["BTC-USD"];
    const need = state.rules.votes_needed;
    if (!sig || !sig.votes) {
      $("signal-meta").textContent = sig ? "Not enough price history yet." : "";
      return;
    }
    $("signal-meta").textContent = `Based on daily candles up to ${sig.candle_date}, checked at ${timeOf(sig.timestamp)} with BTC at ${usd(sig.price)}.`;
    const votes = Object.entries(sig.votes);
    $("votes").innerHTML = votes
      .map(
        ([name, v]) => `<tr><td>${esc(name)}</td><td class="r">${v.value === null ? "–" : v.value.toLocaleString("en-US")}</td>
          <td class="vote vote-${esc(v.vote)}">${esc(v.vote.charAt(0) + v.vote.slice(1).toLowerCase())}</td><td class="note">${esc(v.rule)}</td></tr>`
      )
      .join("");
    const count = (x) => votes.filter(([, v]) => v.vote === x).length;
    const b = count("BUY"), s = count("SELL"), h = count("HOLD");
    const acts = sig.strength >= need * 25 && sig.signal !== "HOLD";
    $("signal-result").innerHTML = `${b} buy, ${s} sell, ${h} hold, so the overall signal is
      <strong class="vote vote-${esc(sig.signal)}">${esc(sig.signal.toLowerCase())}</strong>.
      ${acts ? "That's enough agreement for the bot to act." : `The bot needs ${need} matching votes before it trades.`}`;
  }

  function lineChart(el, points, { base, markers = [], fmt }) {
    if (points.length < 2) {
      el.innerHTML = `<p class="empty">${points.length ? "One data point so far. The line appears after the next check." : "No data yet."}</p>`;
      return;
    }
    const W = 640, H = 220, M = { t: 10, r: 10, b: 24, l: 84 };
    const PW = W - M.l - M.r, PH = H - M.t - M.b;
    const vals = points.map((p) => p.v).concat(base !== undefined ? [base] : []);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.01 || 1;
    lo -= pad; hi += pad;
    const x = (i) => M.l + (i / (points.length - 1)) * PW;
    const y = (v) => M.t + PH - ((v - lo) / (hi - lo)) * PH;
    const d = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">
      ${ticks.map((t) => `<line class="ax" x1="${M.l}" x2="${M.l + PW}" y1="${y(t)}" y2="${y(t)}"/><text class="tk" x="${M.l - 8}" y="${y(t) + 4}" text-anchor="end">${fmt(t)}</text>`).join("")}
      ${base !== undefined ? `<line class="base" x1="${M.l}" x2="${M.l + PW}" y1="${y(base)}" y2="${y(base)}"/>` : ""}
      <path class="ln" d="${d}"/>
      ${markers.map((m) => {
        const cx = x(m.i), cy = y(points[m.i].v);
        return m.side === "BUY"
          ? `<path class="buy" d="M${cx},${cy + 6} l6,10 h-12 z"><title>${esc(m.title)}</title></path>`
          : `<path class="sell" d="M${cx},${cy - 6} l6,-10 h-12 z"><title>${esc(m.title)}</title></path>`;
      }).join("")}
      <text class="tk" x="${M.l}" y="${H - 6}">${esc(points[0].label)}</text>
      <text class="tk" x="${M.l + PW}" y="${H - 6}" text-anchor="end">${esc(points[points.length - 1].label)}</text>
    </svg>`;
  }

  function renderCharts() {
    const eq = state.equity.map((e) => ({ v: e.value, label: e.timestamp.slice(5, 16) }));
    lineChart($("equity-chart"), eq, { base: state.account.initial, fmt: (v) => "$" + Math.round(v).toLocaleString("en-US") });

    const candles = state.candles["BTC-USD"] || [];
    const pts = candles.map((c) => ({ v: c.close, label: c.t }));
    const byDay = new Map(candles.map((c, i) => [c.t, i]));
    const markers = state.trades
      .filter((t) => t.symbol === "BTC-USD")
      .map((t) => {
        const day = t.timestamp.slice(0, 10);
        const i = byDay.has(day) ? byDay.get(day) : candles.length - 1;
        return { i, side: t.trade_type, title: `${t.trade_type} ${t.timestamp} at ${usd(t.price)}` };
      })
      .filter((m) => m.i >= 0);
    lineChart($("price-chart"), pts, { markers, fmt: (v) => "$" + Math.round(v / 1000) + "k" });
  }

  function renderTrades() {
    if (!state.trades.length) {
      $("trades").innerHTML = `<tr><td colspan="6" class="note">No trades yet in this run. With ${state.rules.votes_needed} of 4 votes required,
        the bot can go days without trading. That is the strategy working as designed.</td></tr>`;
      return;
    }
    $("trades").innerHTML = state.trades
      .map(
        (t) => `<tr><td>${esc(t.timestamp.slice(0, 16))}</td>
          <td class="vote vote-${t.trade_type === "BUY" ? "BUY" : "SELL"}">${t.trade_type === "BUY" ? "Buy" : "Sell"}</td>
          <td class="r">${t.quantity.toFixed(6)}</td><td class="r">${usd(t.price)}</td><td class="r">${usd(t.total_value)}</td>
          <td class="note">${esc(prettyNote(t.notes))}</td></tr>`
      )
      .join("");
  }

  function renderRules() {
    const r = state.rules;
    $("rules-text").textContent =
      `Every ${every(state.check_interval)} the bot pulls the BTC price and the last 300 daily candles from Coinbase. ` +
      `Four indicators (RSI, MACD, a 20/50-day moving average crossover and Bollinger Bands) each vote buy, sell or hold. ` +
      `It buys when at least ${r.votes_needed} vote buy, putting ${r.position_size_pct.toFixed(0)}% of cash in, and sells when ${r.votes_needed} vote sell, ` +
      `or earlier if the price falls ${r.stop_loss_pct.toFixed(0)}% (stop-loss) or rises ${r.take_profit_pct.toFixed(0)}% (take-profit) from the entry.`;
  }

  async function refresh() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      state = await res.json();
      countdown = state.next_check_in;
      renderStatus();
      renderAccount();
      renderPosition();
      renderSignal();
      renderCharts();
      renderTrades();
      renderRules();
    } catch (err) {
      $("status").className = "status off";
      $("status-text").textContent = "Can't reach the server. Retrying…";
    }
  }

  setInterval(() => {
    if (state && countdown !== null && countdown > 0) {
      countdown -= 1;
      renderStatus();
      if (countdown === 0) setTimeout(refresh, 4000);
    }
  }, 1000);
  setInterval(refresh, 30000);

  const post = (url) => fetch(url, { method: "POST" }).then(refresh);
  if ($("btn-start")) $("btn-start").addEventListener("click", () => post("/api/bot/start"));
  if ($("btn-stop")) $("btn-stop").addEventListener("click", () => post("/api/bot/stop"));

  refresh();
})();
