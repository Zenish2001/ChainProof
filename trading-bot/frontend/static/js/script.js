// Auto-update interval (5 seconds)
const UPDATE_INTERVAL = 5000;

// ---------------------------------------------------------------------
// Lightweight inline SVG sparkline renderer — no external chart library.
// Takes an array of numbers, draws a simple line chart scaled to fit.
// ---------------------------------------------------------------------
function renderSparkline(container, values, color) {
    if (!container || !values || values.length < 2) {
        if (container) container.innerHTML = '';
        return;
    }

    const w = 200, h = container.classList.contains('sparkline-sm') ? 32 : 44;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = (max - min) || 1;

    const points = values.map((v, i) => {
        const x = (i / (values.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - 4) - 2;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    container.innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
            <polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5" />
        </svg>
    `;
}

// NEW: terminal ticker bar at the top of the page — fetches its own small
// slice of data independently, so it doesn't need to be threaded through
// the other update functions.
async function updateTicker() {
    const el = document.getElementById('tickerText');
    if (!el) return;
    try {
        const [priceRes, portfolioRes, statsRes] = await Promise.all([
            fetch('/api/prices'), fetch('/api/portfolio'), fetch('/api/stats')
        ]);
        const prices = await priceRes.json();
        const portfolio = await portfolioRes.json();
        const stats = await statsRes.json();

        const parts = [];
        if (prices['BTC-USD']) parts.push(`BTC-USD $${prices['BTC-USD'].price.toLocaleString()}`);
        if (portfolio && typeof portfolio.pnl_percent === 'number') {
            const sign = portfolio.pnl_percent >= 0 ? '+' : '';
            parts.push(`PORTFOLIO ${sign}${portfolio.pnl_percent.toFixed(2)}%`);
        }
        if (stats && stats.win_rate !== null && stats.win_rate !== undefined) {
            parts.push(`WIN RATE ${stats.win_rate}%`);
        }
        parts.push('PAPER TRADING');
        el.textContent = parts.join('   \u00b7   ');
    } catch (error) {
        console.error('Error updating ticker:', error);
    }
}

// Update portfolio data
async function updatePortfolio() {
    try {
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        
        // Update total value
        document.getElementById('totalValue').textContent = 
            `$${data.total_value.toLocaleString()}`;
        
        // Update P&L
        const pnlEl = document.getElementById('pnlValue');
        const pnlPercentEl = document.getElementById('pnlPercent');
        const pnlClass = data.pnl >= 0 ? 'positive' : 'negative';
        
        pnlEl.textContent = `${data.pnl >= 0 ? '+' : ''}$${Math.abs(data.pnl).toLocaleString()}`;
        pnlEl.className = `hero-stat-value ${pnlClass}`;
        
        pnlPercentEl.textContent = `${data.pnl >= 0 ? '+' : ''}${data.pnl_percent.toFixed(2)}%`;
        pnlPercentEl.className = `hero-stat-sub ${pnlClass}`;

        // Update the top-level hero change indicator too
        const totalChangeEl = document.getElementById('totalChange');
        if (totalChangeEl) {
            totalChangeEl.textContent = `${data.pnl_percent >= 0 ? '+' : ''}${data.pnl_percent.toFixed(2)}%`;
            totalChangeEl.className = `hero-change ${pnlClass}`;
        }
        
        // Update cash
        document.getElementById('cashValue').textContent = 
            `$${data.cash.toLocaleString()}`;

        // NEW: cash vs. invested allocation bar — real data, not decoration
        const investedTotal = Object.values(data.holdings || {}).reduce((sum, h) => sum + h.current_value, 0);
        const totalForAlloc = data.cash + investedTotal;
        if (totalForAlloc > 0) {
            const cashPct = (data.cash / totalForAlloc) * 100;
            const investedPct = 100 - cashPct;
            const allocCashEl = document.getElementById('allocCash');
            const allocInvestedEl = document.getElementById('allocInvested');
            const allocCashPctEl = document.getElementById('allocCashPct');
            const allocInvestedPctEl = document.getElementById('allocInvestedPct');
            if (allocCashEl) allocCashEl.style.width = `${cashPct}%`;
            if (allocInvestedEl) allocInvestedEl.style.width = `${investedPct}%`;
            if (allocCashPctEl) allocCashPctEl.textContent = `${cashPct.toFixed(0)}%`;
            if (allocInvestedPctEl) allocInvestedPctEl.textContent = `${investedPct.toFixed(0)}%`;
        }
        
        // Update holdings table
        updateHoldings(data.holdings);
        
    } catch (error) {
        console.error('Error updating portfolio:', error);
    }
}

// Update holdings table
function updateHoldings(holdings) {
    const tbody = document.getElementById('holdingsTable');
    
    if (!holdings || Object.keys(holdings).length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="empty-row">
                    No positions yet - Start trading to see holdings!
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = Object.entries(holdings).map(([symbol, data]) => {
        const pnl = data.current_value - data.cost_basis;
        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
        
        return `
            <tr>
                <td><strong>${symbol}</strong></td>
                <td>${data.quantity.toFixed(6)}</td>
                <td>$${data.current_value.toFixed(2)}</td>
                <td class="${pnlClass}">
                    ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}
                </td>
            </tr>
        `;
    }).join('');
}

// Update trades table
async function updateTrades() {
    try {
        const response = await fetch('/api/trades');
        const trades = await response.json();
        
        const tbody = document.getElementById('tradesTable');
        
        if (trades.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-row">
                        No trades yet - Start paper trading to see activity!
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = trades.map(trade => `
            <tr>
                <td>${trade.timestamp}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td>
                    <span class="badge badge-${trade.action.toLowerCase()}">
                        ${trade.action}
                    </span>
                </td>
                <td>${trade.quantity}</td>
                <td>$${trade.price.toLocaleString()}</td>
                <td>$${trade.total.toLocaleString()}</td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error updating trades:', error);
    }
}

// Update prices (+ mini sparklines)
async function updatePrices() {
    try {
        const response = await fetch('/api/prices');
        const prices = await response.json();
        
        const grid = document.getElementById('pricesGrid');
        const symbols = {
            'BTC-USD': { name: 'Bitcoin', index: 0 },
            'ETH-USD': { name: 'Ethereum', index: 1 },
            'SOL-USD': { name: 'Solana', index: 2 }
        };
        
        Object.entries(symbols).forEach(([symbol, info]) => {
            const card = grid.children[info.index];
            const data = prices[symbol];
            
            if (data) {
                card.querySelector('.crypto-price').textContent = 
                    `$${data.price.toLocaleString()}`;
                const changeEl = card.querySelector('.crypto-change');
                const isPositive = data.change_24h >= 0;
                changeEl.textContent = 
                    `${isPositive ? '+' : ''}$${data.change_24h.toFixed(2)}`;
                changeEl.className = `crypto-change ${isPositive ? 'positive' : 'negative'}`;
            }
        });
        
    } catch (error) {
        console.error('Error updating prices:', error);
    }
}

// NEW: mini price sparklines, from real price_history
async function updatePriceSparklines() {
    try {
        const response = await fetch('/api/price_history');
        const history = await response.json();

        document.querySelectorAll('.sparkline-sm[data-symbol]').forEach(el => {
            const symbol = el.getAttribute('data-symbol');
            const series = (history[symbol] || []).map(p => p.close);
            renderSparkline(el, series, '#33C6E0');
        });
    } catch (error) {
        console.error('Error updating price sparklines:', error);
    }
}

// NEW: portfolio value sparkline in the hero section (also reused for the
// smaller P&L trend sparkline, since both trace the same underlying curve)
async function updatePortfolioSparkline() {
    try {
        const response = await fetch('/api/portfolio/history');
        const history = await response.json();
        const series = history.map(p => p.value);

        renderSparkline(document.getElementById('portfolioSparkline'), series, '#E8B84B');

        const pnlSparkEl = document.getElementById('pnlSparkline');
        if (pnlSparkEl) renderSparkline(pnlSparkEl, series, '#33C6E0');
    } catch (error) {
        console.error('Error updating portfolio sparkline:', error);
    }
}

// NEW: current signal per symbol (BUY/SELL/HOLD + strength)
async function updateSignals() {
    try {
        const response = await fetch('/api/signals');
        const signals = await response.json();
        const grid = document.getElementById('signalsGrid');

        const symbols = Object.keys(signals);
        if (symbols.length === 0) {
            grid.innerHTML = '<p class="empty-note">No signal data yet — start the bot to generate one.</p>';
            return;
        }

        grid.innerHTML = symbols.map(symbol => {
            const s = signals[symbol];
            const badgeClass = s.signal.toLowerCase();
            return `
                <div class="signal-card">
                    <div class="signal-symbol">${symbol}</div>
                    <span class="signal-badge ${badgeClass}">${s.signal}</span>
                    <div class="strength-bar-track">
                        <div class="strength-bar-fill" style="width: ${s.strength}%;"></div>
                    </div>
                    <div class="signal-strength-label">${s.strength.toFixed(0)}% strength</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error updating signals:', error);
    }
}

// Countdown state, ticks locally every second and resyncs from server on refresh
let countdownSeconds = null;
let countdownTimerStarted = false;

function formatCountdown(seconds) {
    if (seconds === null || seconds === undefined) return '';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `Next check in ${m}:${s.toString().padStart(2, '0')}`;
}

function tickCountdown() {
    const el = document.getElementById('statusCountdown');
    if (countdownSeconds !== null && countdownSeconds > 0) {
        countdownSeconds -= 1;
        if (el) el.textContent = formatCountdown(countdownSeconds);
    } else if (el) {
        el.textContent = '';
    }
}

if (!countdownTimerStarted) {
    setInterval(tickCountdown, 1000);
    countdownTimerStarted = true;
}

// Update bot status
async function updateBotStatus() {
    try {
        const response = await fetch('/api/bot/status');
        const data = await response.json();
        
        const statusEl = document.getElementById('botStatus');
        const modeEl = document.getElementById('botMode');
        const countdownEl = document.getElementById('statusCountdown');
        
        if (data.running) {
            statusEl.innerHTML = '<span class="live-dot" id="liveDot"></span>Running';
            statusEl.className = 'status-value running';
        } else {
            statusEl.innerHTML = '<span class="live-dot" id="liveDot"></span>Stopped';
            statusEl.className = 'status-value';
        }
        
        modeEl.textContent = data.mode;

        if (typeof data.next_check_in === 'number') {
            countdownSeconds = data.next_check_in;
            if (countdownEl) countdownEl.textContent = formatCountdown(countdownSeconds);
        } else {
            countdownSeconds = null;
            if (countdownEl) countdownEl.textContent = '';
        }
        
    } catch (error) {
        console.error('Error updating bot status:', error);
    }
}

// NEW: session performance stats (win rate, session Sharpe, total return)
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        const winRateEl = document.getElementById('winRate');
        const winRateSubEl = document.getElementById('winRateSub');
        const sharpeEl = document.getElementById('sharpeSession');
        const returnEl = document.getElementById('totalReturn');

        if (data.win_rate !== null && data.win_rate !== undefined) {
            winRateEl.textContent = `${data.win_rate}%`;
            winRateSubEl.textContent = `${data.wins}W / ${data.losses}L (${data.closed_trades} closed)`;
        } else {
            winRateEl.textContent = '—';
            winRateSubEl.textContent = 'no closed trades yet';
        }

        sharpeEl.textContent = (data.sharpe_session !== null && data.sharpe_session !== undefined)
            ? data.sharpe_session.toFixed(2)
            : '—';

        if (data.total_return_pct !== null && data.total_return_pct !== undefined) {
            const isPos = data.total_return_pct >= 0;
            returnEl.textContent = `${isPos ? '+' : ''}${data.total_return_pct}%`;
            returnEl.className = `perf-value ${isPos ? 'positive-text' : 'negative-text'}`;
        } else {
            returnEl.textContent = '—';
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Non-blocking status message instead of alert()
function showBotMessage(message) {
    const el = document.getElementById('botMessage');
    if (!el) return;
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(showBotMessage._t);
    showBotMessage._t = setTimeout(() => el.classList.remove('show'), 4000);
}

// Start bot
async function startBot() {
    try {
        const response = await fetch('/api/bot/start', { method: 'POST' });
        const data = await response.json();
        showBotMessage(data.message);
        updateBotStatus();
    } catch (error) {
        showBotMessage('Error starting bot: ' + error.message);
    }
}

// Stop bot
async function stopBot() {
    try {
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const data = await response.json();
        showBotMessage(data.message);
        updateBotStatus();
    } catch (error) {
        showBotMessage('Error stopping bot: ' + error.message);
    }
}

// Refresh all data
function refreshAll() {
    updatePortfolio();
    updateTrades();
    updatePrices();
    updateBotStatus();
    updatePriceSparklines();
    updatePortfolioSparkline();
    updateSignals();
    updateStats();
    updateTicker();
}

// Event listeners
document.getElementById('startBtn').addEventListener('click', startBot);
document.getElementById('stopBtn').addEventListener('click', stopBot);
document.getElementById('refreshBtn').addEventListener('click', refreshAll);

// Initial load
refreshAll();

// Auto-update every 5 seconds
setInterval(refreshAll, UPDATE_INTERVAL);

console.log('Dashboard loaded! Auto-refreshing every 5 seconds...');