// Auto-update interval (5 seconds)
const UPDATE_INTERVAL = 5000;

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
        pnlEl.className = `stat-value ${pnlClass}`;
        
        pnlPercentEl.textContent = `${data.pnl >= 0 ? '+' : ''}${data.pnl_percent.toFixed(2)}%`;
        pnlPercentEl.className = `stat-change ${pnlClass}`;
        
        // Update cash
        document.getElementById('cashValue').textContent = 
            `$${data.cash.toLocaleString()}`;
        
        // Update holdings table
        updateHoldings(data.holdings);
        
        // Update last update time
        document.getElementById('lastUpdate').textContent = data.last_update;
        
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
                <td colspan="4" style="text-align: center; color: #999;">
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
                    <td colspan="6" style="text-align: center; color: #999;">
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

// Update prices
async function updatePrices() {
    try {
        const response = await fetch('/api/prices');
        const prices = await response.json();
        
        const grid = document.getElementById('pricesGrid');
        const symbols = {
            'BTC-USD': { name: '₿ Bitcoin', index: 0 },
            'ETH-USD': { name: 'Ξ Ethereum', index: 1 },
            'SOL-USD': { name: '◎ Solana', index: 2 }
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

// Update bot status
async function updateBotStatus() {
    try {
        const response = await fetch('/api/bot/status');
        const data = await response.json();
        
        const statusEl = document.getElementById('botStatus');
        const modeEl = document.getElementById('botMode');
        
        if (data.running) {
            statusEl.textContent = '▶️ Running';
            statusEl.style.color = '#10b981';
        } else {
            statusEl.textContent = '⏸️ Stopped';
            statusEl.style.color = '#ef4444';
        }
        
        modeEl.textContent = data.mode;
        
    } catch (error) {
        console.error('Error updating bot status:', error);
    }
}

// Start bot
async function startBot() {
    try {
        const response = await fetch('/api/bot/start', { method: 'POST' });
        const data = await response.json();
        alert(data.message);
        updateBotStatus();
    } catch (error) {
        alert('Error starting bot: ' + error.message);
    }
}

// Stop bot
async function stopBot() {
    try {
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const data = await response.json();
        alert(data.message);
        updateBotStatus();
    } catch (error) {
        alert('Error stopping bot: ' + error.message);
    }
}

// Refresh all data
function refreshAll() {
    updatePortfolio();
    updateTrades();
    updatePrices();
    updateBotStatus();
}

// Event listeners
document.getElementById('startBtn').addEventListener('click', startBot);
document.getElementById('stopBtn').addEventListener('click', stopBot);
document.getElementById('refreshBtn').addEventListener('click', refreshAll);

// Initial load
refreshAll();

// Auto-update every 5 seconds
setInterval(refreshAll, UPDATE_INTERVAL);

console.log('🚀 Dashboard loaded! Auto-refreshing every 5 seconds...');