"""Dashboard API endpoints for SOL Swap."""
import json
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from loguru import logger


router = APIRouter()


def _get_analytics(request: Request):
    """Get analytics store from app state."""
    analytics = getattr(request.app.state, "analytics", None)
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")
    return analytics


def _get_account_manager(request: Request):
    """Get account manager from app state."""
    manager = getattr(request.app.state, "account_manager", None)
    if not manager:
        raise HTTPException(status_code=500, detail="Account manager not initialized")
    return manager


async def _get_token_metadata(request: Request) -> Dict[str, Dict[str, Any]]:
    """Fetch and cache token metadata (symbol/name) keyed by mint."""
    cached = getattr(request.app.state, "token_metadata", None)
    cached_at = getattr(request.app.state, "token_metadata_ts", None)
    if cached and cached_at:
        if datetime.now(timezone.utc) - cached_at < timedelta(hours=6):
            return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://token.jup.ag/all")
            resp.raise_for_status()
            data = resp.json()
            metadata = {
                token.get("address"): token
                for token in data
                if token.get("address")
            }
            request.app.state.token_metadata = metadata
            request.app.state.token_metadata_ts = datetime.now(timezone.utc)
            return metadata
    except Exception as e:
        logger.warning("Failed to fetch token metadata: {}", e)
        return cached or {}


@router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Serve dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SOL Swap Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #1a1a1a;
                color: #fff;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            h1 {
                color: #00d4aa;
                display: inline-block;
                margin: 0;
            }
            .header-container {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 26px;
                gap: 20px;
                padding-top: 6px;
            }
            .brand {
                display: flex;
                align-items: center;
                gap: 12px;
                min-width: 180px;
            }
            .logo {
                width: 46px;
                height: 46px;
                flex: 0 0 auto;
            }
            .logo-ring {
                fill: none;
                stroke: #00d4aa;
                stroke-width: 2.5;
            }
            .logo-swap {
                fill: none;
                stroke: #66f0d2;
                stroke-width: 2.2;
                stroke-linecap: round;
                stroke-linejoin: round;
            }
            .logo-dot {
                fill: #0b1b17;
                stroke: #00d4aa;
                stroke-width: 1.5;
            }
            .logo-sol {
                fill: #0f2b22;
                stroke: #00d4aa;
                stroke-width: 1.6;
            }
            .logo-sol-text {
                fill: #00d4aa;
                font-size: 9px;
                font-family: Arial, sans-serif;
                font-weight: bold;
                letter-spacing: 0.4px;
            }
            .price-charts {
                flex: 1;
                display: grid;
                grid-template-columns: repeat(2, minmax(200px, 1fr));
                gap: 12px;
                margin-top: 10px;
            }
            .price-card {
                background: #202020;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 10px 12px;
            }
            .price-body {
                display: flex;
                align-items: flex-start;
                gap: 12px;
            }
            .price-meta {
                display: flex;
                flex-direction: column;
                min-width: 90px;
            }
            .price-header {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                margin-bottom: 2px;
            }
            .price-title {
                font-size: 12px;
                color: #aaa;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }
            .price-value {
                font-size: 16px;
                font-weight: 600;
            }
            .price-change {
                font-size: 13px;
                font-weight: 600;
                margin-top: 2px;
            }
            .price-change.up { color: #00d4aa; }
            .price-change.down { color: #ff6666; }
            .price-chart {
                width: 100%;
                height: 86px;
                margin-top: -16px;
            }
            .clock-container {
                text-align: right;
                font-family: monospace;
            }
            .clock-nl {
                font-size: 20px;
                font-weight: bold;
                color: #00d4aa;
            }
            .clock-utc {
                font-size: 12px;
                color: #888;
                margin-top: 5px;
            }
            .loading {
                color: #aaa;
                font-size: 12px;
                opacity: 0.8;
            }
            .section {
                background: #2a2a2a;
                padding: 20px;
                margin: 12px 0;
                border-radius: 8px;
            }
            .section h2 {
                margin-top: 0;
            }
            .section-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            .section-header h2 {
                margin: 0;
            }
            .swaps-controls select {
                background: #1f1f1f;
                color: #fff;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }
            .swaps-totals {
                margin-top: 6px;
                color: #aaa;
                font-size: 12px;
            }
            .asset-tabs {
                display: flex;
                gap: 10px;
                margin: 10px 0 14px;
                flex-wrap: wrap;
            }
            .asset-tab {
                background: #242424;
                border: 1px solid #3a3a3a;
                color: #d6d6d6;
                padding: 6px 12px;
                border-radius: 999px;
                font-size: 12px;
                cursor: pointer;
                transition: all 0.15s ease;
            }
            .asset-tab.active {
                background: #0f2b22;
                border-color: #00d4aa;
                color: #00d4aa;
                box-shadow: 0 0 0 1px rgba(0, 212, 170, 0.2);
            }
            .asset-tab:hover {
                border-color: #00d4aa;
            }
            .signal-pill {
                display: inline-flex;
                align-items: center;
                padding: 2px 8px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.2px;
                background: rgba(255, 255, 255, 0.06);
                color: #e5e5e5;
            }
            .signal-type-mr-low { background: rgba(0, 200, 255, 0.15); color: #7fe4ff; }
            .signal-type-mean { background: rgba(255, 206, 86, 0.15); color: #ffd56e; }
            .signal-type-conf { background: rgba(0, 212, 127, 0.15); color: #60e6a9; }
            .signal-type-trend { background: rgba(0, 168, 255, 0.15); color: #7fc8ff; }
            .signal-type-unknown { background: rgba(255, 255, 255, 0.08); color: #cfcfcf; }
            .signal-timeframe { background: rgba(255, 255, 255, 0.08); color: #cfd5ff; }
            .total-value {
                font-size: 14px;
                font-weight: 600;
                color: #00d4aa;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #444;
                font-size: 13px;
            }
            th {
                background: #333;
                color: #00d4aa;
            }
            .success, .completed { color: #00d4aa; }
            .error, .failed { color: #ff4444; }
            .pending { color: #ffaa00; }
            .change-up { color: #00d4aa; }
            .change-down { color: #ff6666; }
            .change-flat { color: #aaa; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-container">
                <div class="brand">
                    <svg class="logo" viewBox="0 0 48 48" aria-label="SOL Swap logo" role="img">
                        <defs>
                            <linearGradient id="sol-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" stop-color="#14F195"/>
                                <stop offset="100%" stop-color="#9945FF"/>
                            </linearGradient>
                        </defs>
                        <circle class="logo-ring" cx="24" cy="24" r="21"/>
                        <path class="logo-swap" d="M14 20h12a6 6 0 0 1 6 6v4"/>
                        <path class="logo-swap" d="M34 28H22a6 6 0 0 1-6-6v-4"/>
                        <polyline class="logo-swap" points="30,32 34,28 30,24"/>
                        <polyline class="logo-swap" points="18,16 14,20 18,24"/>
                        <circle class="logo-dot" cx="14" cy="20" r="2.4"/>
                        <circle class="logo-dot" cx="34" cy="28" r="2.4"/>
                        <rect x="17" y="18" width="14" height="4" rx="2" fill="url(#sol-gradient)"/>
                        <rect x="17" y="24" width="14" height="4" rx="2" fill="url(#sol-gradient)"/>
                        <rect x="17" y="30" width="14" height="4" rx="2" fill="url(#sol-gradient)"/>
                    </svg>
                    <h1>SOL Swap</h1>
                </div>
                <div class="price-charts">
                    <div class="price-card" id="price-card-sol">
                        <div class="price-header">
                            <div class="price-title" id="price-title-0">Token (24h)</div>
                        </div>
                        <div class="price-body">
                            <div class="price-meta">
                                <div class="price-value" id="price-value-0">$--</div>
                                <div class="price-change" id="price-change-0">--</div>
                            </div>
                            <div class="price-chart" id="price-chart-0"></div>
                        </div>
                    </div>
                    <div class="price-card" id="price-card-skr">
                        <div class="price-header">
                            <div class="price-title" id="price-title-1">Token (24h)</div>
                        </div>
                        <div class="price-body">
                            <div class="price-meta">
                                <div class="price-value" id="price-value-1">$--</div>
                                <div class="price-change" id="price-change-1">--</div>
                            </div>
                            <div class="price-chart" id="price-chart-1"></div>
                        </div>
                    </div>
                </div>
                <div class="clock-container">
                    <div class="clock-nl" id="clock-nl">--:--:-- --</div>
                    <div class="clock-utc" id="clock-utc">UTC: --:--:--</div>
                </div>
            </div>
            <div class="asset-tabs" id="asset-tabs"></div>
            <div class="section">
                <div class="section-header">
                    <h2>💰 Wallet Balances</h2>
                    <div id="balances-total" class="total-value">Total Value: --</div>
                </div>
                <div id="balances" class="loading">Loading...</div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2>Recent Swaps</h2>
                    <div class="swaps-controls">
                        <label for="swaps-limit" style="color:#aaa;font-size:12px;margin-right:6px;">Show</label>
                        <select id="swaps-limit">
                            <option value="10" selected>10</option>
                            <option value="25">25</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </select>
                    </div>
                </div>
                <div id="swaps-totals" class="swaps-totals">Totals since --: --</div>
                <div id="swaps">Loading...</div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2>Recent Signals</h2>
                    <div class="swaps-controls">
                        <label for="signals-sort" style="color:#aaa;font-size:12px;margin-right:6px;">Sort</label>
                        <select id="signals-sort">
                            <option value="time" selected>Time</option>
                            <option value="type">Type</option>
                            <option value="timeframe">Timeframe</option>
                        </select>
                    </div>
                </div>
                <div id="signals">Loading...</div>
            </div>
        </div>

        <script>
            let assets = [];
            let currentAsset = null;
            let currentTokens = ["SOL", "SKR"];

            // Format dates in Newfoundland Time (12-hour format)
            function formatNLTime(dateString) {
                // Handle legacy timestamps without timezone info by treating them as UTC
                if (dateString && !dateString.includes('+') && !dateString.endsWith('Z')) {
                    dateString = dateString + 'Z';
                }
                return new Date(dateString).toLocaleString('en-US', {
                    timeZone: 'America/St_Johns',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: 'numeric',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true
                });
            }

            // Update live clocks
            function updateClocks() {
                const now = new Date();

                // Newfoundland Time
                const nlTime = now.toLocaleString('en-US', {
                    timeZone: 'America/St_Johns',
                    hour: 'numeric',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true
                });
                document.getElementById('clock-nl').textContent = nlTime;

                // UTC Time
                const utcTime = now.toLocaleString('en-US', {
                    timeZone: 'UTC',
                    hour: 'numeric',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true
                });
                document.getElementById('clock-utc').textContent = 'UTC: ' + utcTime;
            }

            // Update clocks every second
            updateClocks();
            setInterval(updateClocks, 1000);

            let lastBalancesHtml = null;
            let lastBalancesTotal = null;

            function renderSparkline(prices, width = 220, height = 86) {
                if (!prices || prices.length < 2) {
                    return '<div style="color:#666;font-size:12px;">No data yet</div>';
                }

                const values = prices.map(p => p.price);
                const min = Math.min(...values);
                const max = Math.max(...values);
                const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
                const range = max - min || 1;

                const points = prices.map((p, i) => {
                    const x = (i / (prices.length - 1)) * (width - 4) + 2;
                    const y = height - ((p.price - min) / range) * height;
                    const above = p.price >= mean;
                    return { x, y, above };
                });

                const segments = [];
                let current = [points[0]];
                let currentAbove = points[0].above;

                for (let i = 1; i < points.length; i++) {
                    const point = points[i];
                    if (point.above === currentAbove) {
                        current.push(point);
                    } else {
                        // start a new segment including the last point for continuity
                        segments.push({ above: currentAbove, points: current });
                        current = [points[i - 1], point];
                        currentAbove = point.above;
                    }
                }
                segments.push({ above: currentAbove, points: current });

                const polylines = segments.map(seg => {
                    const stroke = seg.above ? "#00d4aa" : "#ff6666";
                    const segPoints = seg.points
                        .map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)}`)
                        .join(" ");
                    return `<polyline points="${segPoints}" fill="none" stroke="${stroke}" stroke-width="2" />`;
                }).join("");

                return `
                    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
                        ${polylines}
                    </svg>
                `;
            }

            function updatePriceCard(index, symbol, data) {
                const prices = data.prices || [];
                const current = data.current_price ?? null;
                const changePct = data.change_pct ?? null;
                const upper = (symbol || "").toUpperCase();
                const priceDecimals = upper === "SOL" || upper === "USDC" ? 2 : 4;

                const valueEl = document.getElementById(`price-value-${index}`);
                const changeEl = document.getElementById(`price-change-${index}`);
                const chartEl = document.getElementById(`price-chart-${index}`);
                const titleEl = document.getElementById(`price-title-${index}`);

                if (current === null) {
                    valueEl.textContent = "$--";
                    changeEl.textContent = "--";
                    chartEl.innerHTML = renderSparkline(prices);
                    if (titleEl) {
                        titleEl.textContent = symbol ? `${symbol} (24h)` : "Token (24h)";
                    }
                    return;
                }

                if (titleEl) {
                    titleEl.textContent = symbol ? `${symbol} (24h)` : "Token (24h)";
                }
                valueEl.textContent = `$${current.toFixed(priceDecimals)}`;
                if (changePct === null) {
                    changeEl.textContent = "--";
                    changeEl.className = "price-change";
                } else {
                    const sign = changePct >= 0 ? "+" : "";
                    changeEl.textContent = `${sign}${changePct.toFixed(2)}%`;
                    changeEl.className = `price-change ${changePct >= 0 ? "up" : "down"}`;
                }

                chartEl.innerHTML = renderSparkline(prices);
            }

            async function loadPriceCharts() {
                const symbols = currentTokens || [];
                if (!symbols.length) {
                    for (let i = 0; i < 2; i += 1) {
                        updatePriceCard(i, "", {});
                    }
                    return;
                }
                const response = await fetch(`/api/price-history?symbols=${symbols.join(",")}`);
                const data = await response.json();
                if (data && data.data) {
                    for (let i = 0; i < 2; i += 1) {
                        const symbol = symbols[i];
                        if (!symbol) {
                            updatePriceCard(i, "", {});
                            continue;
                        }
                        updatePriceCard(i, symbol, data.data[symbol] || {});
                    }
                }
            }

            function setActiveAsset(assetId) {
                currentAsset = assets.find(asset => asset.id === assetId) || assets[0] || null;
                if (!currentAsset) {
                    return;
                }
                currentTokens = currentAsset.price_symbols || [];
                if (!currentTokens.length && currentAsset.token_pair) {
                    currentTokens = currentAsset.token_pair.split("-").filter(Boolean);
                }
                const tabsEl = document.getElementById('asset-tabs');
                if (tabsEl) {
                    Array.from(tabsEl.querySelectorAll('.asset-tab')).forEach(tab => {
                        tab.classList.toggle('active', tab.dataset.assetId === currentAsset.id);
                    });
                }
                loadSwaps();
                loadSignals();
                loadBalances();
                loadPriceCharts();
            }

            async function loadAssets() {
                const tabsEl = document.getElementById('asset-tabs');
                if (!tabsEl) return;
                const response = await fetch('/api/assets');
                const data = await response.json();
                assets = data.assets || [];
                if (!assets.length) {
                    assets = [{
                        id: "wallet-1",
                        label: "Default",
                        token_pair: "SOL-SKR",
                        price_symbols: ["SOL", "SKR"]
                    }];
                }
                tabsEl.innerHTML = assets.map(asset => `
                    <button class="asset-tab" data-asset-id="${asset.id}">
                        ${asset.label || asset.token_pair || asset.id}
                    </button>
                `).join('');
                Array.from(tabsEl.querySelectorAll('.asset-tab')).forEach(tab => {
                    tab.addEventListener('click', () => setActiveAsset(tab.dataset.assetId));
                });
                setActiveAsset(assets[0].id);
            }

            async function loadSwaps() {
                const limitEl = document.getElementById('swaps-limit');
                const limit = limitEl ? limitEl.value : 10;
                const accountId = currentAsset ? currentAsset.id : null;
                const response = await fetch(`/api/swaps?limit=${limit}${accountId ? `&account_id=${accountId}` : ''}`);
                const data = await response.json();

                const html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Time (NST/NDT)</th>
                                <th>Account</th>
                                <th>Swap</th>
                                <th>Amount</th>
                                <th>USD Value</th>
                                <th>Fee (USD)</th>
                                <th>Change</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.swaps.map((swap, index) => {
                                const inputUsd = swap.input_usd || 0;
                                const outputUsd = swap.output_usd || 0;
                                const usdDisplay = swap.status === 'COMPLETED'
                                    ? `$${inputUsd.toFixed(2)} → $${outputUsd.toFixed(2)}`
                                    : `$${inputUsd.toFixed(2)}`;
                                const feeDisplay = swap.fee_usd == null
                                    ? '-'
                                    : (Number(swap.fee_usd) < 0.01
                                        ? '<$0.01'
                                        : `$${Number(swap.fee_usd).toFixed(2)}`);
                                let changeDisplay = '-';
                                let changeClass = 'change-flat';
                                if (swap.change_pct != null) {
                                    const changePct = Number(swap.change_pct);
                                    const sign = changePct > 0 ? '+' : '';
                                    changeDisplay = `${sign}${changePct.toFixed(2)}%`;
                                    if (changePct > 0) changeClass = 'change-up';
                                    else if (changePct < 0) changeClass = 'change-down';
                                }

                                return `
                                <tr>
                                    <td>${formatNLTime(swap.created_at)}</td>
                                    <td>${swap.account_label || swap.account_id}</td>
                                    <td>${swap.input_token} → ${swap.output_token}</td>
                                    <td>${swap.input_amount.toFixed(4)} → ${(swap.output_amount || 0).toFixed(4)}</td>
                                    <td>${usdDisplay}</td>
                                    <td>${feeDisplay}</td>
                                    <td class="${changeClass}">${changeDisplay}</td>
                                    <td class="${swap.status.toLowerCase()}">${swap.status}</td>
                                </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('swaps').innerHTML = html;

                const totalsEl = document.getElementById('swaps-totals');
                if (totalsEl) {
                    const totals = data.totals || {};
                    const parts = Object.keys(totals).sort().map(token => {
                        const pct = totals[token].change_pct;
                        if (pct === undefined || pct === null) {
                            return `${token}: -`;
                        }
                        const sign = pct > 0 ? '+' : '';
                        return `${token}: ${sign}${pct.toFixed(2)}%`;
                    });
                    const startLabel = data.totals_start
                        ? `${formatNLTime(data.totals_start)} NST`
                        : 'now';
                    totalsEl.textContent = parts.length
                        ? `Totals since ${startLabel}: ${parts.join(' | ')}`
                        : `Totals since ${startLabel}: -`;
                }
            }

            async function loadBalances() {
                const balancesEl = document.getElementById("balances");
                try {
                    const accountId = currentAsset ? currentAsset.id : "wallet-1";
                    const response = await fetch(`/api/balances/${accountId}`);
                    if (!response.ok) {
                        if (lastBalancesHtml) {
                            balancesEl.innerHTML = lastBalancesHtml;
                            balancesEl.classList.add("loading");
                        } else {
                            balancesEl.innerHTML = '<div class="loading">Failed to load balances</div>';
                        }
                        return;
                    }
                    const data = await response.json();

                    let totalUsd = data.total_usd || 0;
                    lastBalancesTotal = totalUsd;
                    document.getElementById("balances-total").textContent = `Total Value: $${totalUsd.toFixed(2)} USD`;
                    balancesEl.classList.remove("loading");
                    const html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Token</th>
                                <th>Balance</th>
                                <th>Price (USD)</th>
                                <th>Value (USD)</th>
                                <th>Δ USD</th>
                                <th>Δ Qty</th>
                                <th>Change</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(data.balances || []).map(b => {
                                const isSol = b.token === "SOL"
                                    || b.mint === "So11111111111111111111111111111111111111112";
                                const priceDecimals = isSol ? 2 : 4;
                                return `
                                <tr>
                                    <td>${b.token}</td>
                                    <td>${b.balance.toFixed(6)}</td>
                                    <td>$${(b.price_usd || 0).toFixed(priceDecimals)}</td>
                                    <td>$${(b.value_usd || 0).toFixed(4)}</td>
                                    <td class="${(b.change_usd ?? 0) > 0 ? 'change-up' : (b.change_usd ?? 0) < 0 ? 'change-down' : 'change-flat'}">
                                        ${b.change_usd == null ? '-' : `${(b.change_usd > 0 ? '+' : '')}$${Math.abs(Number(b.change_usd)).toFixed(2)}`}
                                    </td>
                                    <td class="${(b.change_amount ?? 0) > 0 ? 'change-up' : (b.change_amount ?? 0) < 0 ? 'change-down' : 'change-flat'}">
                                        ${b.change_amount == null ? '-' : `${(b.change_amount > 0 ? '+' : '')}${Number(b.change_amount).toFixed(6)}`}
                                    </td>
                                    <td class="${(b.change_pct ?? 0) > 0 ? 'change-up' : (b.change_pct ?? 0) < 0 ? 'change-down' : 'change-flat'}">
                                        ${b.change_pct == null ? '-' : `${(b.change_pct > 0 ? '+' : '')}${b.change_pct.toFixed(2)}%`}
                                    </td>
                                </tr>
                                `;
                            }).join("")}
                        </tbody>
                    </table>
                `;
                    balancesEl.innerHTML = html;
                    lastBalancesHtml = html;
                } catch (error) {
                    if (lastBalancesHtml) {
                        balancesEl.innerHTML = lastBalancesHtml;
                        balancesEl.classList.add("loading");
                    } else {
                        balancesEl.innerHTML = '<div class="loading">Failed to load balances</div>';
                    }
                }
            }

            async function loadSignals() {
                const accountId = currentAsset ? currentAsset.id : null;
                const response = await fetch(`/api/signals?limit=10${accountId ? `&account_id=${accountId}` : ''}`);
                const data = await response.json();
                const sortEl = document.getElementById('signals-sort');
                const sortBy = sortEl ? sortEl.value : 'time';
                const signals = (data.signals || []).slice();
                if (sortBy !== 'time') {
                    signals.sort((a, b) => {
                        const aVal = (a[sortBy] || '').toString().toLowerCase();
                        const bVal = (b[sortBy] || '').toString().toLowerCase();
                        if (aVal < bVal) return -1;
                        if (aVal > bVal) return 1;
                        return 0;
                    });
                }

                const html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Time (NST/NDT)</th>
                                <th>Action</th>
                                <th>Symbol</th>
                                <th>Type</th>
                                <th>Timeframe</th>
                                <th>Amount</th>
                                <th>Note</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${signals.map(signal => {
                                const typeRaw = (signal.signal_type || '').toString();
                                const typeKey = typeRaw.toLowerCase().replace(/\\s+/g, '-');
                                const typeClass = typeKey ? `signal-type-${typeKey}` : 'signal-type-unknown';
                                const typeLabel = typeRaw || '-';
                                const tfLabel = signal.timeframe || '-';
                                return `
                                <tr>
                                    <td>${formatNLTime(signal.received_at)}</td>
                                    <td>${signal.action}</td>
                                    <td>${signal.symbol}</td>
                                    <td><span class="signal-pill ${typeClass}">${typeLabel}</span></td>
                                    <td><span class="signal-pill signal-timeframe">${tfLabel}</span></td>
                                    <td>${signal.amount || '-'}</td>
                                    <td>${signal.note || '-'}</td>
                                </tr>
                            `;
                            }).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('signals').innerHTML = html;
            }

            // Load data
            loadAssets();

            // Refresh every 5 seconds
            setInterval(() => {
                if (!currentAsset) {
                    return;
                }
                loadSwaps();
                loadSignals();
                loadBalances();
                loadPriceCharts();
            }, 5000);

            const swapsLimit = document.getElementById('swaps-limit');
            if (swapsLimit) {
                swapsLimit.addEventListener('change', () => loadSwaps());
            }
            const signalsSort = document.getElementById('signals-sort');
            if (signalsSort) {
                signalsSort.addEventListener('change', () => loadSignals());
            }
        </script>
    </body>
    </html>
    """


@router.get("/api/price-history")
async def get_price_history(
    request: Request,
    symbols: str = "SOL,SKR",
) -> Dict[str, Any]:
    """Get 24h price history for one or more symbols."""
    analytics = _get_analytics(request)
    data: Dict[str, Any] = {}

    for raw_symbol in symbols.split(","):
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue

        ticks = analytics.list_price_ticks(symbol=symbol, hours=24)
        current_price = ticks[-1]["price"] if ticks else None
        change_pct = None
        if len(ticks) >= 2 and ticks[0]["price"]:
            change_pct = ((current_price - ticks[0]["price"]) / ticks[0]["price"]) * 100

        data[symbol] = {
            "prices": ticks,
            "current_price": current_price,
            "change_pct": change_pct,
        }

    return {"data": data}


@router.get("/api/swaps")
async def get_swaps(
    request: Request,
    limit: int = 10,
    account_id: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Get swap history with historical USD values."""
    analytics = _get_analytics(request)

    swaps = analytics.list_swaps(
        account_id=account_id,
        status=status,
        limit=limit,
    )

    # USD values are already stored in the database from trade time
    # Just ensure they have default values if null
    for swap in swaps:
        if swap.get("input_usd") is None:
            swap["input_usd"] = 0
        if swap.get("output_usd") is None:
            swap["output_usd"] = 0
        swap["change_pct"] = None
        if swap.get("status") == "COMPLETED" and swap.get("output_amount"):
            prev = analytics.get_previous_completed_swap(
                account_id=swap["account_id"],
                output_token=swap["output_token"],
                before_created_at=swap["created_at"],
            )
            if prev and prev.get("output_amount"):
                prev_out = float(prev["output_amount"])
                if prev_out != 0:
                    swap["change_pct"] = ((float(swap["output_amount"]) - prev_out) / prev_out) * 100
    # Totals since configured start (default: app start time)
    totals_start = getattr(request.app.state, "totals_start", None)
    if totals_start is None:
        totals_start = datetime.now(timezone.utc)
        request.app.state.totals_start = totals_start
    start_iso = totals_start.astimezone(timezone.utc).isoformat()
    totals = analytics.get_output_change_totals(since_iso=start_iso, account_id=account_id)

    return {"swaps": swaps, "totals": totals, "totals_start": start_iso}


@router.get("/api/signals")
async def get_signals(
    request: Request,
    limit: int = 50,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get recent signals."""
    analytics = _get_analytics(request)

    signals = analytics.list_signals(
        account_id=account_id,
        limit=limit,
    )

    for signal in signals:
        raw_payload = signal.get("raw_payload") or "{}"
        try:
            payload = json.loads(raw_payload)
        except Exception:
            payload = {}
        signal["signal_type"] = payload.get("signal_type")
        signal["timeframe"] = payload.get("timeframe")

    return {"signals": signals}


@router.get("/api/assets")
async def get_assets(request: Request) -> Dict[str, Any]:
    """Get configured assets for dashboard tabs."""
    manager = _get_account_manager(request)
    assets = []

    for account in manager.accounts.values():
        strategy = account.strategy or {}
        token_pair = strategy.get("token_pair", "")
        base_token = strategy.get("base_token")
        quote_token = strategy.get("quote_token")
        price_symbols = []

        if token_pair and "-" in token_pair:
            for sym in token_pair.split("-"):
                if sym and sym not in price_symbols:
                    price_symbols.append(sym)
        else:
            for sym in (quote_token, base_token):
                if sym and sym not in price_symbols:
                    price_symbols.append(sym)

        label = token_pair or (f"{quote_token}-{base_token}" if quote_token and base_token else account.label)

        assets.append({
            "id": account.id,
            "label": label,
            "token_pair": token_pair,
            "base_token": base_token,
            "quote_token": quote_token,
            "price_symbols": price_symbols,
        })

    return {"assets": assets}


@router.get("/api/balances/{account_id}")
async def get_balances(
    request: Request,
    account_id: str,
) -> Dict[str, Any]:
    """Get token balances for an account with USD values."""
    manager = _get_account_manager(request)
    
    account = manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get token configuration
    config = getattr(request.app.state, "config", {})
    tokens = config.get("tokens", {})
    
    # Get Jupiter and Solana clients
    jupiter = getattr(request.app.state, "jupiter", None)
    solana = getattr(request.app.state, "solana", None)
    
    if not jupiter or not solana:
        raise HTTPException(status_code=500, detail="Clients not initialized")
    
    balances = []
    symbol_by_mint = {mint: symbol for symbol, mint in tokens.items() if mint}
    symbol_overrides = {
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
        "BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups": "URANUS",
        "pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn": "PUMP",
    }
    token_metadata = await _get_token_metadata(request)

    # Get SOL balance
    from solders.pubkey import Pubkey
    from spl.token.constants import TOKEN_PROGRAM_ID
    try:
        from spl.token_2022.constants import TOKEN_2022_PROGRAM_ID
    except Exception:
        TOKEN_2022_PROGRAM_ID = None

    wallet_pubkey = account.keypair.pubkey()
    try:
        sol_balance_resp = await solana.get_balance(wallet_pubkey)
        sol_balance = sol_balance_resp / 1e9 if sol_balance_resp else 0
        if sol_balance > 0:
            balances.append({
                "token": "SOL",
                "name": "Solana",
                "balance": sol_balance,
                "mint": tokens.get("SOL", "So11111111111111111111111111111111111111112"),
            })
    except Exception as e:
        logger.error("Failed to get SOL balance: {}", e)

    # Get all SPL token balances (non-zero)
    mint_balances: Dict[str, float] = {}
    program_ids = [str(TOKEN_PROGRAM_ID)]
    if TOKEN_2022_PROGRAM_ID:
        program_ids.append(str(TOKEN_2022_PROGRAM_ID))
    else:
        # Fallback Token-2022 program id for environments without spl.token_2022
        program_ids.append("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")

    rpc_url = getattr(solana, "rpc_url", None) or config.get("solana", {}).get("rpc_url")
    if rpc_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for program_id in program_ids:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            str(wallet_pubkey),
                            {"programId": program_id},
                            {"encoding": "jsonParsed"},
                        ],
                    }
                    resp = await client.post(rpc_url, json=payload)
                    data = resp.json()
                    if data.get("error"):
                        logger.error("Failed to list token balances: {}", data["error"])
                        continue
                    for item in (data.get("result", {}) or {}).get("value", []):
                        info = (((item.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
                        mint = info.get("mint")
                        token_amount = info.get("tokenAmount") or {}
                        ui_amount = token_amount.get("uiAmount")
                        ui_amount_str = token_amount.get("uiAmountString")
                        if ui_amount is None or (ui_amount == 0 and ui_amount_str not in (None, "", "0", "0.0")):
                            try:
                                ui_amount = float(ui_amount_str or 0)
                            except Exception:
                                ui_amount = 0
                        if not mint or not ui_amount or ui_amount <= 0:
                            continue
                        mint_balances[mint] = mint_balances.get(mint, 0) + float(ui_amount)
        except Exception as e:
            logger.error("Failed to list token balances: {}", e)
    else:
        logger.warning("Solana RPC URL not configured; skipping token balances")

    for mint, balance in mint_balances.items():
        if balance <= 0:
            continue
        meta = token_metadata.get(mint, {})
        symbol = (
            meta.get("symbol")
            or symbol_overrides.get(mint)
            or symbol_by_mint.get(mint)
            or f"{mint[:4]}...{mint[-4:]}"
        )
        name = meta.get("name")
        balances.append({
            "token": symbol,
            "name": name,
            "balance": balance,
            "mint": mint,
        })

    # Get USD prices from Jupiter (API key configured)
    token_mints = [b["mint"] for b in balances]
    prices = {}

    try:
        price_data = await jupiter.get_token_price(token_mints)
        if price_data:
            prices = price_data
    except Exception as e:
        logger.error("Failed to get token prices: {}", str(e))
    
    # Add USD values
    total_usd = 0
    for balance in balances:
        mint = balance["mint"]
        price = prices.get(mint, 0)
        usd_value = balance["balance"] * price
        balance["price_usd"] = price
        balance["value_usd"] = usd_value
        total_usd += usd_value

    # Initialize baseline tracking for balance and USD changes
    baselines = getattr(request.app.state, "balance_baselines", None)
    if baselines is None:
        baselines = {}
        request.app.state.balance_baselines = baselines
    account_baseline = baselines.setdefault(account_id, {})

    for balance in balances:
        mint = balance["mint"]
        baseline_entry = account_baseline.get(mint)
        if baseline_entry is None:
            baseline_entry = {
                "balance": balance["balance"],
                "usd": balance["value_usd"],
            }
            account_baseline[mint] = baseline_entry
        elif not isinstance(baseline_entry, dict):
            # Backward compatibility for old in-memory baseline format (float balance).
            baseline_entry = {
                "balance": float(baseline_entry),
                "usd": float(baseline_entry) * balance["price_usd"],
            }
            account_baseline[mint] = baseline_entry

        base_balance = baseline_entry.get("balance", 0)
        base_usd = baseline_entry.get("usd", 0)

        change_amount = balance["balance"] - base_balance
        balance["change_amount"] = change_amount
        balance["change_usd"] = balance["value_usd"] - base_usd

        if base_balance and base_balance != 0:
            balance["change_pct"] = (change_amount / base_balance) * 100
        else:
            balance["change_pct"] = None
    
    return {
        "account_id": account_id,
        "account_label": account.label,
        "wallet_address": str(wallet_pubkey),
        "balances": balances,
        "total_usd": total_usd,
    }
