let allCommitments = [];
let lastVerificationResults = null;
let lastVerifiedTime = null;

// Scroll-spy: highlights the sidebar nav link for whichever section is
// currently most in view, so it's clear which part of the page you're on.
function setupScrollSpy() {
    const sections = Array.from(document.querySelectorAll('section[id]'));
    const navLinks = Array.from(document.querySelectorAll('.sidebar-nav a[data-section]'));
    if (sections.length === 0 || navLinks.length === 0) return;

    function updateActive() {
        let current = sections[0].id;
        const scrollPos = window.scrollY + 140; // offset for comfortable trigger point

        for (const section of sections) {
            if (section.offsetTop <= scrollPos) {
                current = section.id;
            }
        }

        navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('data-section') === current);
        });
    }

    window.addEventListener('scroll', updateActive);
    updateActive();
}

async function loadSummary() {
    try {
        const res = await fetch('/api/summary');
        const data = await res.json();

        document.getElementById('statReturn').textContent =
            data.return_pct !== undefined ? `+${data.return_pct}%` : '—';
        document.getElementById('statSharpe').textContent =
            data.sharpe !== undefined ? data.sharpe.toFixed(2) : '—';
        document.getElementById('statWinRate').textContent =
            data.win_rate !== undefined ? `${data.win_rate.toFixed(1)}%` : '—';
        document.getElementById('statCommitments').textContent =
            `${data.succeeded_commitments}/${data.total_commitments}`;

        if (data.contract_address) {
            const link = document.getElementById('contractLink');
            link.href = `https://sepolia.etherscan.io/address/${data.contract_address}`;
        }

        if (data.signer_address) {
            document.getElementById('attestationSigner').textContent = data.signer_address;
        }

        const ticker = document.getElementById('tickerText');
        if (ticker) {
            const parts = [];
            if (data.return_pct !== undefined) parts.push(`BACKTEST +${data.return_pct}%`);
            parts.push(`${data.succeeded_commitments}/${data.total_commitments} ON-CHAIN`);
            parts.push('SEPOLIA TESTNET');
            ticker.textContent = 'CHAINPROOF   \u00b7   ' + parts.join('   \u00b7   ');
        }
    } catch (err) {
        console.error('Error loading summary:', err);
    }
}

function renderPriceChart(rows) {
    const container = document.getElementById('priceChart');
    if (!container || rows.length < 2) return;

    const w = 1000, h = 180, pad = 20;
    const prices = rows.map(r => parseFloat(r.price));
    const min = Math.min(...prices), max = Math.max(...prices);
    const range = (max - min) || 1;

    const points = prices.map((p, i) => {
        const x = pad + (i / (prices.length - 1)) * (w - pad * 2);
        const y = h - pad - ((p - min) / range) * (h - pad * 2);
        return { x, y, action: rows[i].action, price: p, index: rows[i].index };
    });

    const linePoints = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

    const dots = points.map(p => {
        const isEntry = p.action === 'BUY';
        const color = isEntry ? '#3D6BC0' : '#B39355';
        return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4" fill="${color}" stroke="#12161C" stroke-width="1.5">
            <title>#${p.index} ${p.action} @ $${p.price.toFixed(2)}</title>
        </circle>`;
    }).join('');

    container.innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
            <polyline points="${linePoints}" fill="none" stroke="#232830" stroke-width="1.5" />
            ${dots}
        </svg>
    `;
}

function renderCommitmentsTable(rows) {
    const tbody = document.getElementById('commitmentsTable');

    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-row">No commitments match this filter</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map(r => {
        const shortHash = r.commitment_hash ? r.commitment_hash.slice(0, 16) + '...' : '—';
        const txLink = r.tx_hash && r.tx_hash !== 'FAILED'
            ? `<a href="https://sepolia.etherscan.io/tx/${r.tx_hash}" target="_blank">${r.tx_hash.slice(0, 10)}...</a>`
            : 'FAILED';
        const badgeClass = `badge-${(r.action || '').toLowerCase()}`;
        const price = parseFloat(r.price);

        return `
            <tr>
                <td>${r.index}</td>
                <td>${r.timestamp}</td>
                <td><span class="${badgeClass}">${r.action}</span></td>
                <td>$${price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td>${shortHash}</td>
                <td>${txLink}</td>
            </tr>
        `;
    }).join('');
}

async function loadCommitments() {
    try {
        const res = await fetch('/api/commitments');
        allCommitments = await res.json();
        renderCommitmentsTable(allCommitments);
        renderPriceChart(allCommitments);
    } catch (err) {
        console.error('Error loading commitments:', err);
    }
}

function applyActionFilter() {
    const selected = document.getElementById('actionFilter').value;
    const filtered = selected === 'ALL'
        ? allCommitments
        : allCommitments.filter(r => r.action === selected);
    renderCommitmentsTable(filtered);
}

function updateLastVerifiedLabel() {
    const el = document.getElementById('lastVerified');
    if (!lastVerifiedTime) return;
    const seconds = Math.floor((Date.now() - lastVerifiedTime) / 1000);
    let label;
    if (seconds < 5) label = 'just now';
    else if (seconds < 60) label = `${seconds}s ago`;
    else label = `${Math.floor(seconds / 60)}m ago`;
    el.textContent = `Last verified: ${label}`;
    el.classList.remove('hidden');
}
setInterval(updateLastVerifiedLabel, 1000);

function downloadReport() {
    if (!lastVerificationResults) return;
    const payload = {
        generated_at: new Date().toISOString(),
        contract_address: document.getElementById('contractLink').href.split('/').pop(),
        ...lastVerificationResults,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chainproof-verification-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

async function runVerification() {
    const btn = document.getElementById('runVerificationBtn');
    const downloadBtn = document.getElementById('downloadReportBtn');
    const statusEl = document.getElementById('verificationStatus');
    const resultsEl = document.getElementById('verificationResults');

    btn.disabled = true;
    btn.textContent = 'Running...';
    statusEl.className = 'status-banner loading';
    statusEl.textContent = 'Re-running strategy code and fetching from the live contract — this takes a moment...';
    resultsEl.innerHTML = '';

    try {
        const res = await fetch('/api/run-verification', { method: 'POST' });
        const data = await res.json();

        statusEl.className = data.matches === data.total ? 'status-banner success' : 'status-banner error';
        statusEl.textContent = `${data.matches}/${data.total} commitments verified successfully`;

        resultsEl.innerHTML = data.results.map(r => `
            <div class="result-chip ${r.match ? 'match' : 'mismatch'}" title="#${r.index} ${r.action}">
                ${r.index}
            </div>
        `).join('');

        lastVerificationResults = data;
        lastVerifiedTime = Date.now();
        updateLastVerifiedLabel();
        downloadBtn.classList.remove('hidden');
    } catch (err) {
        statusEl.className = 'status-banner error';
        statusEl.textContent = 'Error running verification: ' + err.message;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run Verification';
    }
}

async function runTamperTest() {
    const btn = document.getElementById('runTamperBtn');
    const statusEl = document.getElementById('tamperStatus');
    const resultsEl = document.getElementById('tamperResults');

    btn.disabled = true;
    btn.textContent = 'Running...';
    statusEl.className = 'status-banner loading';
    statusEl.textContent = 'Running genuine and tampered checks against the live contract...';
    resultsEl.classList.add('hidden');

    try {
        const res = await fetch('/api/run-tamper-test', { method: 'POST' });
        const data = await res.json();

        const bothCorrect = data.genuine_match && data.tamper_detected;
        statusEl.className = bothCorrect ? 'status-banner success' : 'status-banner error';
        statusEl.textContent = bothCorrect
            ? 'Genuine data verified correctly, and tampering was correctly detected.'
            : 'Something is off — check the details below.';

        document.getElementById('tamperGenuine').innerHTML = `
            <div class="tamper-row"><span>Action</span><span class="val">${data.action}</span></div>
            <div class="tamper-row"><span>Price</span><span class="val">$${data.original_price.toFixed(2)}</span></div>
            <div class="tamper-row"><span>Recomputed</span><span class="val">${data.genuine_hash.slice(0, 14)}...</span></div>
            <div class="tamper-row"><span>On-chain</span><span class="val">${data.onchain_hash.slice(0, 14)}...</span></div>
            <div class="tamper-result ${data.genuine_match ? 'match' : 'mismatch'}">
                ${data.genuine_match ? 'MATCH — as expected' : 'MISMATCH — unexpected!'}
            </div>
        `;

        document.getElementById('tamperTampered').innerHTML = `
            <div class="tamper-row"><span>Tampered price</span><span class="val">$${data.tampered_price.toFixed(2)} (+$${data.tamper_delta})</span></div>
            <div class="tamper-row"><span>Recomputed</span><span class="val">${data.tampered_hash.slice(0, 14)}...</span></div>
            <div class="tamper-row"><span>On-chain (real)</span><span class="val">${data.onchain_hash.slice(0, 14)}...</span></div>
            <div class="tamper-result ${data.tamper_detected ? 'match' : 'mismatch'}">
                ${data.tamper_detected ? 'MISMATCH — tampering correctly detected!' : 'MATCH — tamper NOT detected!'}
            </div>
        `;

        resultsEl.classList.remove('hidden');
    } catch (err) {
        statusEl.className = 'status-banner error';
        statusEl.textContent = 'Error running tamper test: ' + err.message;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run Tamper Test';
    }
}

document.getElementById('runVerificationBtn').addEventListener('click', runVerification);
document.getElementById('runTamperBtn').addEventListener('click', runTamperTest);
document.getElementById('downloadReportBtn').addEventListener('click', downloadReport);
document.getElementById('actionFilter').addEventListener('change', applyActionFilter);

loadSummary();
loadCommitments();
setupScrollSpy();