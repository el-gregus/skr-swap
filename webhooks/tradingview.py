"""TradingView webhook handler for SKR Swap."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status
from loguru import logger

from models.schemas import Signal


router = APIRouter()

def parse_signal_name(signal_name: str) -> Dict[str, Any]:
    """
    Parse signal name format: ACTION|TYPE|TIMEFRAME|SYMBOL|SIGNALTIME
    Example: BUY|MR-Low|5m|SKR-USDC|2026-01-31T12:00:00Z
    """
    parts = [p.strip() for p in signal_name.split("|")]
    if len(parts) < 5:
        raise ValueError("Signal name must have 5 parts: ACTION|TYPE|TIMEFRAME|SYMBOL|SIGNALTIME")

    action, signal_type, timeframe, symbol, signal_time = parts[:5]
    return {
        "action": action.upper(),
        "signal_type": signal_type,
        "timeframe": timeframe,
        "symbol": symbol,
        "signal_time": signal_time,
    }


def parse_webhook_payload(body: bytes, content_type: Optional[str]) -> Dict[str, Any]:
    """
    Parse webhook payload from TradingView.

    Supports:
    - JSON format: {"action": "BUY", "symbol": "SKR-USDC", "amount": 10.0}
    - CSV format: action=BUY,symbol=SKR-USDC,amount=10.0
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
        "symbol": "SKR-USDC",
        "amount": 1.0  (optional),
        "note": "some note"  (optional)
    }
    """
    # Get request body
    body = await request.body()
    content_type = request.headers.get("content-type")

    # Parse payload
    payload = parse_webhook_payload(body, content_type)

    action = payload.get("action", "").upper()
    symbol = payload.get("symbol")
    signal_meta: Dict[str, Any] = {}

    # Support signal name pattern: ACTION|TYPE|TIMEFRAME|SYMBOL|SIGNALTIME
    signal_name = payload.get("signal") or payload.get("signal_name") or payload.get("alert_name")
    if signal_name:
        try:
            parsed = parse_signal_name(str(signal_name))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid signal name: {e}"
            )
        action = parsed["action"]
        symbol = parsed["symbol"]
        signal_meta.update({
            "signal_type": parsed["signal_type"],
            "timeframe": parsed["timeframe"],
            "signal_time": parsed["signal_time"],
        })

    # Validate required fields
    if action not in ("BUY", "SELL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {action}. Must be BUY or SELL."
        )

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
        metadata={**payload, **signal_meta},
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
