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
@router.get("", response_class=HTMLResponse)
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
            h1 { color: #00d4aa; }
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
            <h1>🔄 SKR Swap Dashboard</h1>

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
            async function loadSwaps() {
                const response = await fetch('/api/swaps?limit=10');
                const data = await response.json();

                const html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Account</th>
                                <th>Swap</th>
                                <th>Amount</th>
                                <th>Status</th>
                                <th>Signature</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.swaps.map(swap => `
                                <tr>
                                    <td>${new Date(swap.created_at).toLocaleString()}</td>
                                    <td>${swap.account_label || swap.account_id}</td>
                                    <td>${swap.input_token} → ${swap.output_token}</td>
                                    <td>${swap.input_amount.toFixed(4)} → ${(swap.output_amount || 0).toFixed(4)}</td>
                                    <td class="${swap.status.toLowerCase()}">${swap.status}</td>
                                    <td>${swap.signature ? swap.signature.slice(0, 16) + '...' : '-'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('swaps').innerHTML = html;
            }

            async function loadSignals() {
                const response = await fetch('/api/signals?limit=10');
                const data = await response.json();

                const html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Action</th>
                                <th>Symbol</th>
                                <th>Amount</th>
                                <th>Note</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.signals.map(signal => `
                                <tr>
                                    <td>${new Date(signal.received_at).toLocaleString()}</td>
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

            // Refresh every 5 seconds
            setInterval(() => {
                loadSwaps();
                loadSignals();
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
    """Get swap history."""
    analytics = _get_analytics(request)

    swaps = analytics.list_swaps(
        account_id=account_id,
        status=status,
        limit=limit,
    )

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
    """Get token balances for an account."""
    analytics = _get_analytics(request)
    manager = _get_account_manager(request)

    account = manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    balances = analytics.get_wallet_balances(account_id)

    return {
        "account_id": account_id,
        "account_label": account.label,
        "balances": balances,
    }
