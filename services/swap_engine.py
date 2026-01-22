"""Swap strategy engine for processing signals."""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any, Optional
from loguru import logger

from models.schemas import Signal, SwapRequest

if TYPE_CHECKING:
    from services.analytics_store import AnalyticsStore


class SwapEngine:
    """Processes trading signals and triggers swaps."""

    def __init__(
        self,
        account_id: str,
        account_label: str,
        strategy: Dict[str, Any],
        analytics: "AnalyticsStore",
        swap_manager: Any,  # Will be set by AccountManager
    ):
        self.account_id = account_id
        self.account_label = account_label
        self.strategy = strategy
        self.analytics = analytics
        self.swap_manager = swap_manager
        self.last_swap_time: Dict[str, datetime] = {}
        self.last_action: Optional[str] = None  # Track last executed action

    async def process_signal(self, signal: Signal) -> None:
        """
        Process a trading signal and execute swap if conditions are met.

        Args:
            signal: Trading signal from webhook
        """
        logger.info(
            "[{}] Processing signal: {} {}",
            self.account_id,
            signal.action,
            signal.symbol
        )

        # Validate signal
        if not self._validate_signal(signal):
            return

        # Check cooldown period
        if not self._check_cooldown(signal.symbol):
            logger.info(
                "[{}] Cooldown active for {}, skipping signal",
                self.account_id,
                signal.symbol
            )
            return

        # Determine swap direction
        input_token, output_token = self._get_swap_tokens(signal)
        if not input_token or not output_token:
            logger.warning("[{}] Could not determine swap tokens", self.account_id)
            return

        # Get swap amount
        amount = signal.amount or self.strategy.get("default_swap_size", 0.1)
        slippage_bps = self.strategy.get("max_slippage_bps", 100)

        # Create swap request
        swap_request = SwapRequest(
            account_id=self.account_id,
            input_token=input_token,
            output_token=output_token,
            amount=amount,
            slippage_bps=slippage_bps,
        )

        # Execute swap
        logger.info(
            "[{}] Executing swap: {} {} → {}",
            self.account_id,
            amount,
            input_token,
            output_token
        )

        result = await self.swap_manager.execute_swap(swap_request)

        if result.success:
            logger.info(
                "[{}] Swap successful: {} (sig: {})",
                self.account_id,
                result.output_amount,
                result.signature[:16] if result.signature else "?"
            )
            self.last_swap_time[signal.symbol] = datetime.utcnow()
            # Update last action after successful swap
            self.last_action = signal.action
        else:
            logger.error(
                "[{}] Swap failed: {}",
                self.account_id,
                result.error
            )

    def _validate_signal(self, signal: Signal) -> bool:
        """Validate signal meets requirements."""
        # Basic validation
        if signal.action not in ("BUY", "SELL"):
            logger.warning("[{}] Invalid signal action: {}", self.account_id, signal.action)
            return False

        # Prevent consecutive duplicate actions
        if self.last_action is not None and signal.action == self.last_action:
            logger.warning(
                "[{}] Rejecting consecutive {} signal (last action was {})",
                self.account_id,
                signal.action,
                self.last_action
            )
            return False

        return True

    def _check_cooldown(self, symbol: str) -> bool:
        """Check if enough time has passed since last swap."""
        min_time_between = self.strategy.get("min_time_between_swaps", 30)
        if min_time_between <= 0:
            return True

        last_swap = self.last_swap_time.get(symbol)
        if not last_swap:
            return True

        elapsed = (datetime.utcnow() - last_swap).total_seconds()
        return elapsed >= min_time_between

    def _get_swap_tokens(self, signal: Signal) -> tuple[str, str]:
        """
        Determine input and output tokens based on signal.

        Args:
            signal: Trading signal

        Returns:
            Tuple of (input_token, output_token)
        """
        base_token = self.strategy.get("base_token", "SOL")
        quote_token = self.strategy.get("quote_token", "SKR")

        if signal.action == "BUY":
            # BUY quote token with base token (SOL → SKR)
            return base_token, quote_token
        else:
            # SELL quote token for base token (SKR → SOL)
            return quote_token, base_token
