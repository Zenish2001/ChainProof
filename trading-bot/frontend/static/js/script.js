// Crypto Trading Bot dashboard.
// Data: /api/prices (tickers), /api/state (paper bot), /api/market/<sym>
// (candles + indicators), /api/backtest (strategy run). Charts are plain SVG.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n, d = 2) => (n < 0 ? "−$" : "$") + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const price = (n) => money(n, n >= 1000 ? 2 : n >= 1 ? 2 : 4);
  const signed = (n) => (n > 0 ? "+" : "") + money(n);
  const pct = (n) => (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(2) + "%";
  const upDown = (n) => (n > 0 ? "up" : n < 0 ? "down" : "");
  const compact = (n) => (Math.abs(n) >= 1000 ? "$" + (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : "$" + n.toFixed(n < 10 ? 2 : 0));
  const every = (sec) => (Math.round(sec / 60) <= 1 ? "minute" : `${Math.round(sec / 60)} minutes`);
  const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const timeOf = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");
  const md = (t) => new Date(t + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const my = (t) => new Date(t + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
  const cap = (s) => (s ? s.charAt(0) + s.slice(1).toLowerCase() : "");

  let botState = null;
  let countdown = null;
  let market = { symbol: "BTC-USD", data: null };
  const layers = { sma20: true, sma50: true, bb: true };

  // ------------------------------------------------------------ tooltip
  const tip = $("tip");
  function showTip(html, ev) {
    tip.innerHTML = html;
    tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - 14;
    if (y + h > window.innerHeight - 8) y = ev.clientY - h - 14;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  const hideTip = () => (tip.hidden = true);

  // ------------------------------------------------------- chart helpers
  function niceTicks(lo, hi, count = 5) {
    const raw = (hi - lo) / count;
    const mag = 10 ** Math.floor(Math.log10(raw || 1));
    const norm = raw / mag;
    const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
    return out;
  }

  function pathFrom(values, x, y) {
    let d = "", pen = false;
    values.forEach((v, i) => {
      if (v === null || v === undefined) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  }

  function frame(el, { W, H, M, n, lo, hi, yFmt, xLabels, rightAxis = true }) {
    const PW = W - M.l - M.r, PH = H - M.t - M.b;
    const step = PW / Math.max(n, 1);
    const x = (i) => M.l + step * (i + 0.5);
    const y = (v) => M.t + PH - ((v - lo) / (hi - lo || 1)) * PH;
    const ticks = niceTicks(lo, hi, 4);
    const ax = rightAxis ? M.l + PW + 8 : M.l - 8;
    const anchor = rightAxis ? "start" : "end";
    let g = ticks
      .map((t) => `<line class="gl" x1="${M.l}" x2="${M.l + PW}" y1="${y(t)}" y2="${y(t)}"/><text class="ax-t" x="${ax}" y="${y(t) + 4}" text-anchor="${anchor}">${yFmt(t)}</text>`)
      .join("");
    if (xLabels) {
      const every = Math.max(1, Math.ceil(n / 6));
      for (let i = Math.floor(every / 2); i < n; i += every) g += `<text class="ax-t" x="${x(i)}" y="${H - 6}" text-anchor="middle">${esc(xLabels(i))}</text>`;
    }
    return { PW, PH, step, x, y, grid: g };
  }

  function mount(el, W, H, inner) {
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${inner}<line class="xh" x1="0" x2="0" y1="0" y2="${H}" visibility="hidden"/><rect class="hit" x="0" y="0" width="${W}" height="${H}" fill="transparent"/></svg>`;
    return el.querySelector("svg");
  }

  function hover(svg, W, n, x, step, html) {
    const xh = svg.querySelector(".xh");
    const hit = svg.querySelector(".hit");
    hit.addEventListener("mousemove", (ev) => {
      const r = svg.getBoundingClientRect();
      const vx = ((ev.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(n - 1, Math.round((vx - x(0)) / step)));
      xh.setAttribute("x1", x(i));
      xh.setAttribute("x2", x(i));
      xh.setAttribute("visibility", "visible");
      showTip(html(i), ev);
    });
    hit.addEventListener("mouseleave", () => {
      xh.setAttribute("visibility", "hidden");
      hideTip();
    });
  }

  // ------------------------------------------------------------- tickers
  let priceTimer = null;
  async function loadPrices() {
    clearTimeout(priceTimer);
    let ok = false;
    try {
      const res = await fetch("/api/prices", { cache: "no-store" });
      if (!res.ok) throw new Error(`server returned ${res.status}`);
      const body = await res.json();
      const data = body.prices || {};
      for (const [sym, p] of Object.entries(data)) {
        if (!p || p.price == null || !$(`px-${sym}`)) continue;
        ok = true;
        $(`px-${sym}`).textContent = price(p.price);
        const ch = $(`ch-${sym}`);
        if (p.change_24h_pct != null) {
          ch.textContent = pct(p.change_24h_pct);
          ch.className = "t-change " + upDown(p.change_24h_pct);
        }
        $(`rg-${sym}`).textContent = p.low_24h != null ? `24h range ${price(p.low_24h)} – ${price(p.high_24h)}` : `via ${p.source || "API"}`;
      }
      $("price-source").textContent = ok
        ? `Live prices, refreshed every 30 seconds. Change is over the last 24 hours.`
        : `Live prices unavailable right now${body.error ? ": " + body.error : ""} Retrying…`;
    } catch (err) {
      $("price-source").textContent = `Couldn't load live prices (${err.message}). Retrying…`;
    }
    // Retry quickly until the first prices arrive, then every 30 seconds.
    priceTimer = setTimeout(loadPrices, ok ? 30000 : 5000);
  }

  // ---------------------------------------------------------- paper bot
  function renderStatus() {
    const s = botState;
    const pill = $("bot-pill");
    pill.textContent = s.running ? "Running" : "Stopped";
    pill.className = "pill " + (s.running ? "on" : "off");

    const coins = (s.symbols || ["BTC-USD"]).map((x) => x.split("-")[0]).join(", ");
    let t = s.running ? `Checks ${coins} every ${every(s.check_interval)}.` : "The bot is stopped.";
    if (s.running && countdown !== null) t += ` Next check in ${mmss(countdown)}.`;
    if (s.last_cycle) t += ` Last check at ${timeOf(s.last_cycle)}.`;
    if (s.last_error) t += ` Last error: ${s.last_error}`;
    $("status-text").innerHTML = `<span class="dot ${s.running ? "on" : ""}"></span>${esc(t)}`;
  }

  function renderBot() {
    const s = botState;
    renderStatus();

    const a = s.account;
    const set = (id, text, n) => {
      $(id).textContent = text;
      $(id).className = n === undefined || n === null ? "" : upDown(n);
    };
    set("acc-total", money(a.total));
    set("acc-return", pct(a.return_pct), a.return_pct);
    set("acc-live", s.live ? pct(s.live.return_pct) : "–", s.live ? s.live.return_pct : null);
    set("acc-hold", s.live && s.live.buy_hold_pct !== null ? pct(s.live.buy_hold_pct) : "–", s.live ? s.live.buy_hold_pct : null);
    set("acc-cash", money(a.cash));
    set("acc-realized", signed(a.realized_pnl), a.realized_pnl);
    set("acc-closed", a.closed_trades ? `${a.closed_trades} (${a.win_rate.toFixed(0)}% won)` : "0");
    set("acc-fees", money(a.fees_paid));
    if (s.live) {
      $("acc-hint").textContent = `Trades BTC, ETH and SOL with $10,000 of pretend money. The first ${s.rules.warm_days} days are a replay of history with the same rules; live trading on real-time Coinbase prices since ${s.live.since.slice(0, 16)} UTC. No real funds.`;
    }

    const r = s.rules;
    if (!s.positions.length) {
      $("position").innerHTML = `<p class="flat">No open positions. The bot is in cash, waiting for ${r.votes_needed} of 4 indicators to say buy on one of the coins.</p>`;
    } else {
      $("position").innerHTML = `<div class="table-wrap"><table class="table compact">
        <thead><tr><th>Coin</th><th class="r">Entry</th><th class="r">Now</th><th class="r">P&amp;L</th><th class="r">Stop</th><th class="r">Target</th><th class="r">Held</th></tr></thead><tbody>
        ${s.positions.map((p) => `<tr><td><b>${esc(p.symbol.split("-")[0])}</b></td><td class="r">${price(p.entry_price)}</td><td class="r">${price(p.price)}</td>
          <td class="r ${upDown(p.unrealized)}">${signed(p.unrealized)}<br><small>${pct(p.unrealized_pct)}</small></td>
          <td class="r down">${price(p.stop_price)}</td><td class="r up">${price(p.target_price)}</td>
          <td class="r">${p.held_days === null ? "–" : p.held_days + "d"}</td></tr>`).join("")}
        </tbody></table></div>`;
    }

    renderEquity();
    renderPaperTrades();
    renderDecisions();
    $("rules-text").textContent =
      `Every ${every(s.check_interval)} the bot pulls live Coinbase prices for ${s.symbols.map((x) => x.split("-")[0]).join(", ")} and the latest daily candles. ` +
      `RSI, MACD, a 20/50-day moving average crossover and Bollinger Bands each vote. When ${r.votes_needed} vote buy, it buys with up to ${r.allocation_pct.toFixed(0)}% of the account; ` +
      `when ${r.votes_needed} vote sell it sells, or earlier at a ${r.stop_loss_pct.toFixed(0)}% stop-loss or ${r.take_profit_pct.toFixed(0)}% take-profit. ` +
      `Every buy and sell pays a ${r.fee_pct.toFixed(1)}% fee.`;
  }

  function renderDecisions() {
    const d = botState.decisions;
    if (!d.length) return;
    const label = { BUY: "Bought", SELL: "Sold (signal)", STOP_LOSS: "Stop-loss hit", TAKE_PROFIT: "Take-profit hit", HOLD: "No trade", IN_POSITION: "Holding", WAIT: "Cooling down", NO_CASH: "No cash left" };
    $("decisions").innerHTML = d
      .map((r) => `<tr><td>${esc(r.source === "replay" ? r.timestamp.slice(5, 10) + " close" : r.timestamp.slice(5, 16))}${r.source === "replay" ? ' <span class="src src-replay">replay</span>' : ""}</td>
        <td>${esc(r.symbol.split("-")[0])}</td><td class="r">${price(r.price)}</td>
        <td><span class="v-BUY">${r.buy_votes}B</span> <span class="v-SELL">${r.sell_votes}S</span> <span class="v-HOLD">${r.hold_votes}H</span></td>
        <td><span class="act act-${esc(r.action)}">${esc(label[r.action] || r.action)}</span></td></tr>`)
      .join("");
  }

  function renderEquity() {
    const pts = botState.equity;
    const el = $("equity-chart");
    if (pts.length < 2) {
      el.innerHTML = `<p class="empty">The value chart starts after the second check.</p>`;
      return;
    }
    const vals = pts.map((p) => p.value).concat([botState.account.initial]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.12 || 50;
    lo -= pad; hi += pad;
    const W = 600, H = 190, M = { t: 14, r: 64, b: 22, l: 6 };
    const f = frame(el, { W, H, M, n: pts.length, lo, hi, yFmt: (v) => "$" + Math.round(v).toLocaleString("en-US"),
      xLabels: (i) => md(pts[i].timestamp.slice(0, 10)) });
    const firstLive = pts.findIndex((p) => p.source !== "replay");
    // Replay part dashed, live part solid; the live line starts at the last replay point so they connect.
    const replayVals = pts.map((p, i) => (firstLive === -1 || i <= firstLive ? p.value : null));
    const liveVals = pts.map((p, i) => (firstLive !== -1 && i >= Math.max(0, firstLive - 1) ? p.value : null));
    let mark = "";
    if (firstLive > 0) {
      const lx = f.x(firstLive);
      const nearEnd = lx > M.l + f.PW * 0.8;
      mark = `<line class="l-live-mark" x1="${lx}" x2="${lx}" y1="${M.t}" y2="${M.t + f.PH}"/><text class="live-label" x="${nearEnd ? lx - 4 : lx + 4}" y="${M.t - 3}" text-anchor="${nearEnd ? "end" : "start"}">${nearEnd ? "live from here" : "live →"}</text>`;
    }
    const svg = mount(el, W, H, `${f.grid}
      <line class="l-base" x1="${M.l}" x2="${M.l + f.PW}" y1="${f.y(botState.account.initial)}" y2="${f.y(botState.account.initial)}"/>
      ${mark}
      <path class="l-replay" d="${pathFrom(replayVals, f.x, f.y)}"/>
      <path class="l-main" d="${pathFrom(liveVals, f.x, f.y)}"/>`);
    hover(svg, W, pts.length, f.x, f.step, (i) => `<b>${money(pts[i].value)}</b><br>${esc(pts[i].timestamp.slice(0, 16))} UTC${pts[i].source === "replay" ? " (replay)" : ""}`);
  }

  function renderPaperTrades() {
    const t = botState.trades;
    if (!t.length) {
      $("trades").innerHTML = `<tr><td colspan="9" class="hint">No trades yet. The 90-day replay runs when the bot first starts, then live trades appear here.</td></tr>`;
      return;
    }
    $("trades").innerHTML = t
      .map((r) => `<tr><td>${esc(r.source === "replay" ? r.timestamp.slice(0, 10) + " close" : r.timestamp.slice(0, 16))}</td><td><b>${esc(r.symbol.split("-")[0])}</b></td>
        <td><span class="tag tag-${r.trade_type === "BUY" ? "BUY" : "SELL"}">${r.trade_type === "BUY" ? "Buy" : "Sell"}</span></td>
        <td class="r">${r.quantity.toFixed(r.quantity < 1 ? 5 : 3)}</td><td class="r">${price(r.price)}</td><td class="r">${money(r.total_value)}</td>
        <td class="r ${r.pnl == null ? "" : upDown(r.pnl)}">${r.pnl == null ? "" : `${signed(r.pnl)}<br><small>${pct(r.pnl_pct)}</small>`}</td>
        <td><span class="src src-${r.source === "replay" ? "replay" : "live"}">${r.source === "replay" ? "Replay" : "Live"}</span></td>
        <td class="hint" style="margin:0">${esc(r.notes || "")}</td></tr>`)
      .join("");
  }

  async function loadBot() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      botState = await res.json();
      countdown = botState.next_check_in;
      renderBot();
      if (market.data && market.symbol === "BTC-USD") renderMarket();
    } catch {
      $("status-text").textContent = "Can't reach the server. Retrying…";
    }
  }

  // ------------------------------------------------------------- market
  function renderMarket() {
    const { symbol, data } = market;
    const c = data.candles;
    $("market-title").textContent = `${symbol} daily`;
    $("signals-title").textContent = `${symbol} signals, last 10 days`;
    if (!c.length) {
      $("candle-chart").innerHTML = `<p class="empty">Not enough price history yet.</p>`;
      return;
    }
    const n = c.length;

    // Price + overlays
    const vals = [];
    const openPos = botState && botState.positions.find((p) => p.symbol === symbol);
    if (openPos) vals.push(openPos.entry_price, openPos.stop_price);
    c.forEach((k) => {
      vals.push(k.l, k.h);
      if (layers.bb && k.bbu) vals.push(k.bbu, k.bbl);
    });
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.05;
    lo -= pad; hi += pad;
    const W = 1100, H = 380, M = { t: 10, r: 70, b: 24, l: 8 };
    const f = frame(null, { W, H, M, n, lo, hi, yFmt: compact, xLabels: (i) => md(c[i].t) });
    const bw = Math.max(1, f.step * 0.62);

    let bb = "";
    if (layers.bb) {
      const pts = c.map((k, i) => (k.bbu ? [i, k.bbu, k.bbl] : null)).filter(Boolean);
      if (pts.length > 1) {
        const top = pts.map(([i, u]) => `${f.x(i).toFixed(1)},${f.y(u).toFixed(1)}`);
        const bot = pts.slice().reverse().map(([i, , l]) => `${f.x(i).toFixed(1)},${f.y(l).toFixed(1)}`);
        bb = `<polygon class="a-bb" points="${top.concat(bot).join(" ")}"/>
              <path class="l-bb" d="${pathFrom(c.map((k) => k.bbu), f.x, f.y)}"/>
              <path class="l-bb" d="${pathFrom(c.map((k) => k.bbl), f.x, f.y)}"/>`;
      }
    }
    const candles = c
      .map((k, i) => {
        const cls = k.c >= k.o ? "c-up" : "c-down";
        const top = f.y(Math.max(k.o, k.c)), bottom = f.y(Math.min(k.o, k.c));
        return `<line class="${cls}" x1="${f.x(i)}" x2="${f.x(i)}" y1="${f.y(k.h)}" y2="${f.y(k.l)}" stroke-width="1"/>
                <rect class="${cls}" x="${f.x(i) - bw / 2}" y="${top}" width="${bw}" height="${Math.max(1, bottom - top)}"/>`;
      })
      .join("");
    const lines =
      (layers.sma20 ? `<path class="l-sma20" d="${pathFrom(c.map((k) => k.sma20), f.x, f.y)}"/>` : "") +
      (layers.sma50 ? `<path class="l-sma50" d="${pathFrom(c.map((k) => k.sma50), f.x, f.y)}"/>` : "");

    // Paper-bot trade markers and open-position levels for this coin
    let marks = "";
    let markCount = 0;
    if (botState) {
      const idx = new Map(c.map((k, i) => [k.t, i]));
      botState.trades.filter((t) => t.symbol === symbol).forEach((t) => {
        const i = idx.get(t.timestamp.slice(0, 10));
        if (i === undefined) return;
        markCount++;
        const k = c[i];
        marks += t.trade_type === "BUY"
          ? `<path class="mk-buy" d="M${f.x(i)},${f.y(k.l) + 6} l6,10 h-12 z"/>`
          : `<path class="mk-sell" d="M${f.x(i)},${f.y(k.h) - 6} l6,-10 h-12 z"/>`;
      });
    }
    const pos = openPos;
    if (pos) {
      [["entry", pos.entry_price, "entry"], ["stop", pos.stop_price, "stop"], ["target", pos.target_price, "target"]].forEach(([k, v, name]) => {
        if (v < lo || v > hi) return;
        marks += `<line class="l-${k}" x1="${M.l}" x2="${M.l + f.PW}" y1="${f.y(v)}" y2="${f.y(v)}"/><text class="lvl lvl-${k}" x="${M.l + 4}" y="${f.y(v) - 4}">${name} ${price(v)}</text>`;
      });
    }
    $("marker-note").textContent = (markCount ? "▲ ▼ paper-bot buys and sells" : "No paper trades on this coin in the chart window") + (pos ? ". Dashed lines: open position entry, stop and target." : "");

    const svg = mount($("candle-chart"), W, H, f.grid + bb + candles + lines + marks);
    hover(svg, W, n, f.x, f.step, (i) => {
      const k = c[i], prev = c[i - 1];
      const ch = prev ? (k.c / prev.c - 1) * 100 : null;
      return `<b>${esc(k.t)}</b><br>Open ${price(k.o)} · High ${price(k.h)}<br>Low ${price(k.l)} · Close ${price(k.c)}` +
        (ch !== null ? ` <span class="${upDown(ch)}">(${pct(ch)})</span>` : "") +
        (k.sma20 ? `<br>SMA 20 ${price(k.sma20)}` : "") + (k.sma50 ? ` · SMA 50 ${price(k.sma50)}` : "");
    });

    renderRsi(c);
    renderMacd(c);
    renderSignals(data.signals);
  }

  function renderRsi(c) {
    const W = 540, H = 150, M = { t: 8, r: 40, b: 20, l: 6 }, n = c.length;
    const f = frame(null, { W, H, M, n, lo: 0, hi: 100, yFmt: (v) => v.toFixed(0), xLabels: null });
    const inner = `${f.grid}
      <rect class="zone" x="${M.l}" width="${f.PW}" y="${f.y(70)}" height="${f.y(30) - f.y(70)}"/>
      <line class="l-base" x1="${M.l}" x2="${M.l + f.PW}" y1="${f.y(70)}" y2="${f.y(70)}"/>
      <line class="l-base" x1="${M.l}" x2="${M.l + f.PW}" y1="${f.y(30)}" y2="${f.y(30)}"/>
      <path class="l-rsi" d="${pathFrom(c.map((k) => k.rsi), f.x, f.y)}"/>`;
    const svg = mount($("rsi-chart"), W, H, inner);
    hover(svg, W, n, f.x, f.step, (i) => {
      const v = c[i].rsi;
      const note = v === null ? "" : v > 70 ? " (overbought, votes sell)" : v < 30 ? " (oversold, votes buy)" : "";
      return `<b>${esc(c[i].t)}</b><br>RSI ${v === null ? "–" : v.toFixed(1)}${note}`;
    });
  }

  function renderMacd(c) {
    const W = 540, H = 150, M = { t: 8, r: 56, b: 20, l: 6 }, n = c.length;
    const vals = c.flatMap((k) => [k.macd, k.macds, k.macdh]).filter((v) => v !== null);
    let lo = Math.min(...vals, 0), hi = Math.max(...vals, 0);
    const pad = (hi - lo) * 0.1 || 1;
    lo -= pad; hi += pad;
    const fmt = (v) => (Math.abs(v) < 1e-9 ? "0" : Math.abs(v) >= 100 ? Math.round(v).toLocaleString("en-US") : v.toFixed(Math.abs(v) >= 1 ? 1 : 3));
    const f = frame(null, { W, H, M, n, lo, hi, yFmt: fmt, xLabels: null });
    const bw = Math.max(1, f.step * 0.6);
    const bars = c
      .map((k, i) => (k.macdh === null ? "" : `<rect class="${k.macdh >= 0 ? "b-pos" : "b-neg"}" x="${f.x(i) - bw / 2}" width="${bw}" y="${Math.min(f.y(k.macdh), f.y(0))}" height="${Math.abs(f.y(k.macdh) - f.y(0))}"/>`))
      .join("");
    const inner = `${f.grid}${bars}
      <path class="l-macd" d="${pathFrom(c.map((k) => k.macd), f.x, f.y)}"/>
      <path class="l-macds" d="${pathFrom(c.map((k) => k.macds), f.x, f.y)}"/>`;
    const svg = mount($("macd-chart"), W, H, inner);
    hover(svg, W, n, f.x, f.step, (i) => {
      const k = c[i];
      if (k.macd === null) return esc(k.t);
      return `<b>${esc(k.t)}</b><br>MACD ${fmt(k.macd)} · Signal ${fmt(k.macds)}<br>${k.macd > k.macds ? "Above signal line, votes buy" : "Below signal line, votes sell"}`;
    });
  }

  function renderSignals(rows) {
    if (!rows.length) {
      $("signal-rows").innerHTML = `<tr><td colspan="7" class="hint">Not enough history yet.</td></tr>`;
      return;
    }
    const v = (x) => `<span class="v v-${esc(x)}">${cap(x)}</span>`;
    $("signal-rows").innerHTML = rows
      .map((r) => `<tr><td>${esc(r.t)}</td><td class="r">${price(r.price)}</td><td>${v(r.rsi)}</td><td>${v(r.macd)}</td><td>${v(r.ma)}</td><td>${v(r.bb)}</td>
        <td><span class="tag tag-${esc(r.overall)}">${cap(r.overall)}${r.overall !== "HOLD" ? ` ${r.strength}%` : ""}</span></td></tr>`)
      .join("");
  }

  const marketCache = {};

  async function fetchMarket(symbol) {
    if (marketCache[symbol] && Date.now() - marketCache[symbol].at < 5 * 60 * 1000) return marketCache[symbol].data;
    const res = await fetch(`/api/market/${symbol}`);
    const data = await res.json();
    marketCache[symbol] = { at: Date.now(), data };
    return data;
  }

  function drawSpark(symbol, candles) {
    const el = $(`sp-${symbol}`);
    if (!el || candles.length < 2) return;
    const pts = candles.slice(-30).map((k) => k.c);
    const lo = Math.min(...pts), hi = Math.max(...pts);
    const x = (i) => (i / (pts.length - 1)) * 120;
    const y = (v) => 33 - ((v - lo) / (hi - lo || 1)) * 30;
    const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
    const dir = pts[pts.length - 1] >= pts[0] ? "up" : "down";
    el.innerHTML = `<path class="f-${dir}" d="${line}L120,36L0,36Z"/><path class="s-${dir}" d="${line}"/>`;
  }

  async function loadSparks() {
    for (const sym of ["BTC-USD", "ETH-USD", "SOL-USD"]) {
      try {
        const d = await fetchMarket(sym);
        drawSpark(sym, d.candles);
      } catch {
        /* sparkline is optional */
      }
    }
  }

  async function loadMarket(symbol) {
    market.symbol = symbol;
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.symbol === symbol)));
    document.querySelectorAll(".ticker").forEach((b) => b.classList.toggle("active", b.dataset.symbol === symbol));
    try {
      const data = await fetchMarket(symbol);
      if (market.symbol !== symbol) return; // user switched again meanwhile
      drawSpark(symbol, data.candles);
      market.data = data;
      renderMarket();
    } catch {
      $("candle-chart").innerHTML = `<p class="empty">Couldn't load ${esc(symbol)} candles. Try again in a moment.</p>`;
    }
  }

  // ----------------------------------------------------------- backtest
  const form = $("bt-form");
  const outs = { position_size: "o-size", stop_loss: "o-sl", take_profit: "o-tp" };
  Object.entries(outs).forEach(([name, id]) => {
    form.elements[name].addEventListener("input", (e) => ($(id).textContent = e.target.value + "%"));
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("bt-run");
    btn.disabled = true;
    btn.textContent = "Running…";
    const body = {
      symbol: form.elements.symbol.value,
      position_size: form.elements.position_size.value / 100,
      stop_loss: form.elements.stop_loss.value / 100,
      take_profit: form.elements.take_profit.value / 100,
    };
    try {
      const res = await fetch("/api/backtest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const r = await res.json();
      if (r.error) throw new Error(r.error);
      renderBacktest(r);
    } catch (err) {
      $("bt-result").innerHTML = `<p class="hint">${esc(err.message || "Backtest failed.")}</p>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Run backtest";
    }
  });

  function renderBacktest(r) {
    const m = r.metrics;
    const beat = m.total_return_pct - r.buy_hold_pct;
    const metric = (label, val, cls = "") => `<div><span>${label}</span><strong class="${cls}">${val}</strong></div>`;
    let html = `<p class="hint">${esc(r.symbol)}, ${esc(r.period[0])} to ${esc(r.period[1])}. ${
      beat >= 0 ? `The strategy beat buying and holding by ${beat.toFixed(1)} points.` : `Buying and holding did ${Math.abs(beat).toFixed(1)} points better.`
    }</p>
      <div class="bt-metrics">
        ${metric("Strategy return", pct(m.total_return_pct), upDown(m.total_return_pct))}
        ${metric("Buy and hold", pct(r.buy_hold_pct), upDown(r.buy_hold_pct))}
        ${metric("Trades", m.total_trades)}
        ${metric("Win rate", m.win_rate.toFixed(0) + "%")}
        ${metric("Sharpe ratio", m.sharpe_ratio.toFixed(2))}
        ${metric("Max drawdown", pct(m.max_drawdown), "down")}
      </div>
      <div class="bt-legend"><span><i></i>Strategy</span><span><i class="alt"></i>Buy and hold</span></div>
      <div id="bt-chart" class="chart"></div>`;
    if (r.trades.length) {
      html += `<h3>Trades (last ${r.trades.length})</h3><div class="table-wrap"><table class="table">
        <thead><tr><th>Entry</th><th>Exit</th><th class="r">Entry price</th><th class="r">Exit price</th><th class="r">P&amp;L</th><th>Exit reason</th></tr></thead><tbody>
        ${r.trades.slice().reverse().map((t) => `<tr><td>${esc(t.entry)}</td><td>${esc(t.exit)}</td><td class="r">${price(t.entry_price)}</td><td class="r">${price(t.exit_price)}</td>
          <td class="r ${upDown(t.pnl)}">${signed(t.pnl)} (${pct(t.pnl_pct)})</td><td>${esc(t.reason.toLowerCase().replace(/_/g, "-"))}</td></tr>`).join("")}
        </tbody></table></div>`;
    } else {
      html += `<p class="hint">No trades with these settings.</p>`;
    }
    $("bt-result").innerHTML = html;

    const eq = r.equity;
    const vals = eq.flatMap((p) => [p.v, p.hold]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.06;
    lo -= pad; hi += pad;
    const W = 1100, H = 240, M = { t: 8, r: 70, b: 22, l: 8 };
    const f = frame(null, { W, H, M, n: eq.length, lo, hi, yFmt: compact, xLabels: (i) => my(eq[i].t) });
    const svg = mount($("bt-chart"), W, H, `${f.grid}
      <line class="l-base" x1="${M.l}" x2="${M.l + f.PW}" y1="${f.y(10000)}" y2="${f.y(10000)}"/>
      <path class="l-alt" d="${pathFrom(eq.map((p) => p.hold), f.x, f.y)}"/>
      <path class="l-main" d="${pathFrom(eq.map((p) => p.v), f.x, f.y)}"/>`);
    hover(svg, W, eq.length, f.x, f.step, (i) => `<b>${esc(eq[i].t)}</b><br>Strategy ${money(eq[i].v)}<br>Buy and hold ${money(eq[i].hold)}`);
  }

  // --------------------------------------------------------------- wiring
  document.querySelectorAll(".tabs button, .ticker").forEach((b) =>
    b.addEventListener("click", () => {
      loadMarket(b.dataset.symbol);
      if (b.classList.contains("ticker")) $("market").scrollIntoView({ behavior: "smooth", block: "start" });
    })
  );
  document.querySelectorAll(".legend input").forEach((cb) =>
    cb.addEventListener("change", () => {
      layers[cb.dataset.layer] = cb.checked;
      if (market.data) renderMarket();
    })
  );
  const post = (url) => fetch(url, { method: "POST" }).then(loadBot);
  if ($("btn-start")) $("btn-start").addEventListener("click", () => post("/api/bot/start"));
  if ($("btn-stop")) $("btn-stop").addEventListener("click", () => post("/api/bot/stop"));

  setInterval(() => {
    if (botState && countdown !== null && countdown > 0) {
      countdown -= 1;
      renderStatus();
      if (countdown === 0) setTimeout(loadBot, 4000);
    }
  }, 1000);
  setInterval(loadBot, 30000);

  loadPrices();
  loadBot();
  loadMarket("BTC-USD").then(loadSparks);
})();
