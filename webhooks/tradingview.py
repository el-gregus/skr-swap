"""TradingView webhook handler for SKR Swap."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status
from loguru import logger

from models.schemas import Signal


router = APIRouter()


def parse_webhook_payload(body: bytes, content_type: Optional[str]) -> Dict[str, Any]:
    """
    Parse webhook payload from TradingView.

    Supports:
    - JSON format: {"action": "BUY", "symbol": "SOL-SKR", "amount": 1.0}
    - CSV format: action=BUY,symbol=SOL-SKR,amount=1.0
    """
    try:
        # Try JSON first
        if content_type and "application/json" in content_type:
            import json
            return json.loads(body.decode("utf-8"))

        # Try CSV format
        text = body.decode("utf-8").strip()
        if "=" in text and "," in text:
            pairs = [p.strip() for p in text.split(",")]
            result = {}
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    result[key.strip()] = value.strip()
            return result

        # Default: try as JSON
        import json
        return json.loads(text)

    except Exception as e:
        logger.error("Failed to parse webhook payload: {}", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload format: {e}"
        )


@router.post("/webhook")
async def webhook(request: Request) -> Dict[str, Any]:
    """
    Receive trading signals from TradingView or other sources.

    Expected payload:
    {
        "action": "BUY" or "SELL",
        "symbol": "SOL-SKR",
        "amount": 1.0  (optional),
        "note": "some note"  (optional)
    }
    """
    # Get request body
    body = await request.body()
    content_type = request.headers.get("content-type")

    # Parse payload
    payload = parse_webhook_payload(body, content_type)

    # Validate required fields
    action = payload.get("action", "").upper()
    if action not in ("BUY", "SELL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {action}. Must be BUY or SELL."
        )

    symbol = payload.get("symbol")
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: symbol"
        )

    # Parse amount
    amount = None
    if amount_raw := payload.get("amount"):
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            logger.warning("Invalid amount value: {}", amount_raw)

    # Create signal
    signal = Signal(
        action=action,
        symbol=symbol,
        amount=amount,
        price=payload.get("price"),
        note=payload.get("note"),
        metadata=payload,
    )

    logger.info("Webhook received: {} {} {}", action, symbol, amount or "")

    # Get signal router from app state
    signal_router = getattr(request.app.state, "signal_router", None)
    if signal_router:
        await signal_router.handle(signal)
    else:
        logger.warning("Signal router not initialized")

    return {
        "status": "received",
        "action": signal.action,
        "symbol": signal.symbol,
        "amount": signal.amount,
    }
