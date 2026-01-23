"""Dashboard API endpoints for SKR Swap."""
from typing import Optional, Dict, Any
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


@router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Serve dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SKR Swap Dashboard</title>
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
            .price-header {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                margin-bottom: 6px;
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
                height: 70px;
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
                margin: 20px 0;
                border-radius: 8px;
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
            }
            th {
                background: #333;
                color: #00d4aa;
            }
            .success { color: #00d4aa; }
            .error { color: #ff4444; }
            .pending { color: #ffaa00; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-container">
                <div class="brand">
                    <svg class="logo" viewBox="0 0 48 48" aria-label="SKR Swap logo" role="img">
                        <circle class="logo-ring" cx="24" cy="24" r="21"/>
                        <path class="logo-swap" d="M14 20h12a6 6 0 0 1 6 6v4"/>
                        <path class="logo-swap" d="M34 28H22a6 6 0 0 1-6-6v-4"/>
                        <polyline class="logo-swap" points="30,32 34,28 30,24"/>
                        <polyline class="logo-swap" points="18,16 14,20 18,24"/>
                        <circle class="logo-dot" cx="14" cy="20" r="2.4"/>
                        <circle class="logo-dot" cx="34" cy="28" r="2.4"/>
                        <circle class="logo-sol" cx="24" cy="24" r="7.5"/>
                        <text class="logo-sol-text" x="24" y="27.5" text-anchor="middle">SOL</text>
                    </svg>
                    <h1>SKR Swap</h1>
                </div>
                <div class="price-charts">
                    <div class="price-card" id="price-card-sol">
                        <div class="price-header">
                            <div class="price-title">SOL (24h)</div>
                        </div>
                        <div class="price-value" id="price-value-sol">$--</div>
                        <div class="price-change" id="price-change-sol">--</div>
                        <div class="price-chart" id="price-chart-sol"></div>
                    </div>
                    <div class="price-card" id="price-card-skr">
                        <div class="price-header">
                            <div class="price-title">SKR (24h)</div>
                        </div>
                        <div class="price-value" id="price-value-skr">$--</div>
                        <div class="price-change" id="price-change-skr">--</div>
                        <div class="price-chart" id="price-chart-skr"></div>
                    </div>
                </div>
                <div class="clock-container">
                    <div class="clock-nl" id="clock-nl">--:--:-- --</div>
                    <div class="clock-utc" id="clock-utc">UTC: --:--:--</div>
                </div>
            </div>
            <div class="section">
                <h2>💰 Wallet Balances</h2>
                <div id="balances" class="loading">Loading...</div>
            </div>

            <div class="section">
                <h2>Recent Swaps</h2>
                <div id="swaps">Loading...</div>
            </div>

            <div class="section">
                <h2>Recent Signals</h2>
                <div id="signals">Loading...</div>
            </div>
        </div>

        <script>
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

            function renderSparkline(prices, width = 240, height = 70) {
                if (!prices || prices.length < 2) {
                    return '<div style="color:#666;font-size:12px;">No data yet</div>';
                }

                const values = prices.map(p => p.price);
                const min = Math.min(...values);
                const max = Math.max(...values);
                const range = max - min || 1;

                const points = prices.map((p, i) => {
                    const x = (i / (prices.length - 1)) * (width - 4) + 2;
                    const y = height - ((p.price - min) / range) * (height - 10) - 5;
                    return `${x.toFixed(2)},${y.toFixed(2)}`;
                }).join(" ");

                return `
                    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
                        <polyline points="${points}" fill="none" stroke="#00d4aa" stroke-width="2" />
                    </svg>
                `;
            }

            function updatePriceCard(symbol, data) {
                const prices = data.prices || [];
                const current = data.current_price ?? null;
                const changePct = data.change_pct ?? null;
                const priceDecimals = symbol === "SOL" ? 2 : 4;

                const valueEl = document.getElementById(`price-value-${symbol.toLowerCase()}`);
                const changeEl = document.getElementById(`price-change-${symbol.toLowerCase()}`);
                const chartEl = document.getElementById(`price-chart-${symbol.toLowerCase()}`);

                if (current === null) {
                    valueEl.textContent = "$--";
                    changeEl.textContent = "--";
                    chartEl.innerHTML = renderSparkline(prices);
                    return;
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
                const response = await fetch('/api/price-history?symbols=SOL,SKR');
                const data = await response.json();
                if (data && data.data) {
                    updatePriceCard("SOL", data.data.SOL || {});
                    updatePriceCard("SKR", data.data.SKR || {});
                }
            }

            async function loadSwaps() {
                const response = await fetch('/api/swaps?limit=10');
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
                                <th>Status</th>
                                <th>Signature</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.swaps.map(swap => {
                                const inputUsd = swap.input_usd || 0;
                                const outputUsd = swap.output_usd || 0;
                                const usdDisplay = swap.status === 'COMPLETED'
                                    ? `$${inputUsd.toFixed(4)} → $${outputUsd.toFixed(4)}`
                                    : `$${inputUsd.toFixed(4)}`;

                                return `
                                <tr>
                                    <td>${formatNLTime(swap.created_at)}</td>
                                    <td>${swap.account_label || swap.account_id}</td>
                                    <td>${swap.input_token} → ${swap.output_token}</td>
                                    <td>${swap.input_amount.toFixed(4)} → ${(swap.output_amount || 0).toFixed(4)}</td>
                                    <td>${usdDisplay}</td>
                                    <td class="${swap.status.toLowerCase()}">${swap.status}</td>
                                    <td>${swap.signature ? swap.signature.slice(0, 16) + '...' : '-'}</td>
                                </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('swaps').innerHTML = html;
            }

            async function loadBalances() {
                const response = await fetch("/api/balances/wallet-1");
                if (!response.ok) {
                    document.getElementById("balances").innerHTML = '<div class="loading">Failed to load balances</div>';
                    return;
                }
                const data = await response.json();

                let totalUsd = data.total_usd || 0;
                const html = `
                    <div style="margin-bottom: 15px;">
                        <strong>Total Value:</strong> $${totalUsd.toFixed(2)} USD
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Token</th>
                                <th>Balance</th>
                                <th>Price (USD)</th>
                                <th>Value (USD)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(data.balances || []).map(b => {
                                const isSol = b.token === "SOL"
                                    || b.mint === "So11111111111111111111111111111111111111112";
                                const priceDecimals = isSol ? 2 : 4;
                                return `
                                <tr>
                                    <td><strong>${b.token}</strong></td>
                                    <td>${b.balance.toFixed(6)}</td>
                                    <td>$${(b.price_usd || 0).toFixed(priceDecimals)}</td>
                                    <td>$${(b.value_usd || 0).toFixed(4)}</td>
                                </tr>
                                `;
                            }).join("")}
                        </tbody>
                    </table>
                `;
                document.getElementById("balances").innerHTML = html;
            }

            async function loadSignals() {
                const response = await fetch('/api/signals?limit=10');
                const data = await response.json();

                const html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Time (NST/NDT)</th>
                                <th>Action</th>
                                <th>Symbol</th>
                                <th>Amount</th>
                                <th>Note</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.signals.map(signal => `
                                <tr>
                                    <td>${formatNLTime(signal.received_at)}</td>
                                    <td>${signal.action}</td>
                                    <td>${signal.symbol}</td>
                                    <td>${signal.amount || '-'}</td>
                                    <td>${signal.note || '-'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('signals').innerHTML = html;
            }

            // Load data
            loadSwaps();
            loadSignals();
            loadBalances();
            loadPriceCharts();

            // Refresh every 5 seconds
            setInterval(() => {
                loadSwaps();
                loadSignals();
                loadBalances();
                loadPriceCharts();
            }, 5000);
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
    limit: int = 100,
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

    return {"swaps": swaps}


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

    return {"signals": signals}


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
    
    # Get SOL balance
    from solders.pubkey import Pubkey
    wallet_pubkey = account.keypair.pubkey()
    
    try:
        sol_balance_resp = await solana.get_balance(wallet_pubkey)
        sol_balance = sol_balance_resp / 1e9 if sol_balance_resp else 0
        
        balances.append({
            "token": "SOL",
            "balance": sol_balance,
            "mint": tokens.get("SOL", "So11111111111111111111111111111111111111112"),
        })
    except Exception as e:
        logger.error("Failed to get SOL balance: {}", e)
    
    # Get SKR balance
    if "SKR" in tokens:
        try:
            skr_balance_raw = await solana.get_token_balance(
                Pubkey.from_string(str(wallet_pubkey)),
                Pubkey.from_string(tokens["SKR"])
            )
            # Handle None (error) vs 0 (no balance)
            if skr_balance_raw is not None:
                decimals = await solana.get_token_decimals(
                    Pubkey.from_string(tokens["SKR"])
                )
                decimals = decimals if decimals is not None else 6
                skr_balance = skr_balance_raw / (10 ** decimals)
            else:
                skr_balance = 0

            balances.append({
                "token": "SKR",
                "balance": skr_balance,
                "mint": tokens["SKR"],
            })
        except Exception as e:
            logger.error("Failed to get SKR balance: {}", str(e))
            # Add entry with 0 balance on error to prevent missing from dashboard
            balances.append({
                "token": "SKR",
                "balance": 0,
                "mint": tokens["SKR"],
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
    
    return {
        "account_id": account_id,
        "account_label": account.label,
        "wallet_address": str(wallet_pubkey),
        "balances": balances,
        "total_usd": total_usd,
    }
