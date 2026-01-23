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
            }
            .header-container {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 20px;
            }
            .clock-container {
                text-align: right;
                font-family: monospace;
            }
            .clock-nl {
                font-size: 24px;
                font-weight: bold;
                color: #00d4aa;
            }
            .clock-utc {
                font-size: 14px;
                color: #888;
                margin-top: 5px;
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
                <h1>🔄 SKR Swap Dashboard</h1>
                <div class="clock-container">
                    <div class="clock-nl" id="clock-nl">--:--:-- --</div>
                    <div class="clock-utc" id="clock-utc">UTC: --:--:--</div>
                </div>
            </div>
            <div class="section">
                <h2>💰 Wallet Balances</h2>
                <div id="balances">Loading...</div>
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
                                const usdDisplay = swap.status === 'completed'
                                    ? `$${inputUsd.toFixed(2)} → $${outputUsd.toFixed(2)}`
                                    : `$${inputUsd.toFixed(2)}`;

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
                            ${(data.balances || []).map(b => `
                                <tr>
                                    <td><strong>${b.token}</strong></td>
                                    <td>${b.balance.toFixed(6)}</td>
                                    <td>$${(b.price_usd || 0).toFixed(2)}</td>
                                    <td>$${(b.value_usd || 0).toFixed(2)}</td>
                                </tr>
                            `).join("")}
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

            // Refresh every 5 seconds
            setInterval(() => {
                loadSwaps();
                loadSignals();
                loadBalances();
            }, 5000);
        </script>
    </body>
    </html>
    """


@router.get("/api/swaps")
async def get_swaps(
    request: Request,
    limit: int = 100,
    account_id: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Get swap history with USD values."""
    analytics = _get_analytics(request)

    swaps = analytics.list_swaps(
        account_id=account_id,
        status=status,
        limit=limit,
    )

    # Get token configuration and Jupiter client
    config = getattr(request.app.state, "config", {})
    tokens = config.get("tokens", {})
    jupiter = getattr(request.app.state, "jupiter", None)

    # Fetch current token prices
    prices = {}
    if jupiter:
        try:
            # Collect unique token mints from swaps
            token_mints = set()
            for swap in swaps:
                input_token = swap.get("input_token")
                output_token = swap.get("output_token")
                if input_token in tokens:
                    token_mints.add(tokens[input_token])
                if output_token in tokens:
                    token_mints.add(tokens[output_token])

            # Fetch prices for all unique tokens
            if token_mints:
                price_data = await jupiter.get_token_price(list(token_mints))
                if price_data:
                    prices = price_data
        except Exception as e:
            logger.error("Failed to fetch token prices for swaps: {}", e)

    # Add USD values to each swap
    for swap in swaps:
        input_token = swap.get("input_token")
        output_token = swap.get("output_token")
        input_amount = swap.get("input_amount", 0)
        output_amount = swap.get("output_amount", 0)

        # Get prices
        input_mint = tokens.get(input_token)
        output_mint = tokens.get(output_token)
        input_price = prices.get(input_mint, 0) if input_mint else 0
        output_price = prices.get(output_mint, 0) if output_mint else 0

        # Calculate USD values
        swap["input_usd"] = input_amount * input_price
        swap["output_usd"] = output_amount * output_price if output_amount else 0

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
                skr_balance = skr_balance_raw / 1e6
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
