"""Swap strategy engine for processing signals."""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any, Optional
from loguru import logger
from solders.pubkey import Pubkey

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
        solana_client: Any = None,
        keypair: Any = None,
        token_config: Dict[str, str] = None,
    ):
        self.account_id = account_id
        self.account_label = account_label
        self.strategy = strategy
        self.analytics = analytics
        self.swap_manager = swap_manager
        self.solana_client = solana_client
        self.keypair = keypair
        self.token_config = token_config or {}
        self.last_swap_time: Dict[str, datetime] = {}
        self.last_action: Optional[str] = None
        self.last_swap_output_amount: Optional[float] = None  # Track SOL from SELL

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

        # Check position before executing (arbitrage strategy)
        if not await self._check_position(signal.action):
            logger.info(
                "[{}] Skipping {} - position check failed",
                self.account_id,
                signal.action
            )
            return

        # Determine swap direction
        input_token, output_token = self._get_swap_tokens(signal)
        if not input_token or not output_token:
            logger.warning("[{}] Could not determine swap tokens", self.account_id)
            return

        # Get swap amount based on action
        amount = await self._get_swap_amount(signal.action, input_token)
        if amount is None or amount <= 0:
            logger.warning(
                "[{}] Invalid or zero swap amount for {} {}",
                self.account_id,
                signal.action,
                input_token
            )
            return

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
            "[{}] Executing swap: {} {} → {} (slippage: {}bps / {}%)",
            self.account_id,
            amount,
            input_token,
            output_token,
            slippage_bps,
            slippage_bps / 100.0
        )

        result = await self.swap_manager.execute_swap(swap_request)

        if result.success:
            logger.info(
                "[{}] Swap successful: {} {} (sig: {})",
                self.account_id,
                result.output_amount,
                output_token,
                result.signature[:16] if result.signature else "?"
            )
            self.last_swap_time[signal.symbol] = datetime.utcnow()
            # Update last action after successful swap
            self.last_action = signal.action
            # Save output amount if this was a SELL (to use for next BUY)
            if signal.action == "SELL":
                self.last_swap_output_amount = result.output_amount
                logger.info(
                    "[{}] Saved {} SOL for next BUY",
                    self.account_id,
                    result.output_amount
                )
        else:
            logger.error(
                "[{}] Swap failed: {}",
                self.account_id,
                result.error
            )

    async def _check_position(self, action: str) -> bool:
        """
        Check if we should execute this action based on current holdings.

        Arbitrage strategy:
        - Only BUY SKR if we don't have any (holding SOL)
        - Only SELL SKR if we have some (holding SKR)

        Args:
            action: BUY or SELL

        Returns:
            True if position check passes, False otherwise
        """
        if not self.solana_client or not self.keypair:
            logger.warning("[{}] Cannot check position: missing client/keypair", self.account_id)
            return True  # Allow trade if we can't check

        skr_mint = self.token_config.get("SKR")
        if not skr_mint:
            logger.warning("[{}] SKR mint not configured", self.account_id)
            return True  # Allow trade if SKR not configured

        try:
            # Get current SKR balance
            balance = await self.solana_client.get_token_balance(
                Pubkey.from_string(str(self.keypair.pubkey())),
                Pubkey.from_string(skr_mint)
            )

            # Convert from lamports to tokens (6 decimals for SKR)
            skr_balance = (balance / 1e6) if balance else 0
            min_threshold = self.strategy.get("min_skr_threshold", 0.1)  # Minimum SKR to consider "holding"

            logger.info(
                "[{}] Current SKR balance: {} (threshold: {})",
                self.account_id,
                skr_balance,
                min_threshold
            )

            if action == "BUY":
                # Only buy if we DON'T have SKR (or very little)
                if skr_balance >= min_threshold:
                    logger.warning(
                        "[{}] Skipping BUY - already holding {} SKR (threshold: {})",
                        self.account_id,
                        skr_balance,
                        min_threshold
                    )
                    return False
                logger.info("[{}] BUY approved - SKR balance below threshold", self.account_id)
                return True

            elif action == "SELL":
                # Only sell if we HAVE SKR
                if skr_balance < min_threshold:
                    logger.warning(
                        "[{}] Skipping SELL - insufficient SKR balance: {} (threshold: {})",
                        self.account_id,
                        skr_balance,
                        min_threshold
                    )
                    return False
                logger.info("[{}] SELL approved - have {} SKR to sell", self.account_id, skr_balance)
                return True

            return True

        except Exception as e:
            logger.error("[{}] Failed to check position: {}", self.account_id, e)
            return False  # Don't trade if we can't verify position

    async def _get_swap_amount(self, action: str, token: str) -> Optional[float]:
        """
        Get the amount to swap based on action.

        For SELL: Use entire SKR balance
        For BUY: Use SOL amount from previous SELL, or default

        Args:
            action: BUY or SELL
            token: Token symbol to swap

        Returns:
            Amount to swap or None if error
        """
        if action == "SELL":
            # Use entire SKR balance
            if not self.solana_client or not self.keypair:
                logger.warning("[{}] Cannot get balance: missing client/keypair", self.account_id)
                return self.strategy.get("default_swap_size", 0.1)

            skr_mint = self.token_config.get("SKR")
            if not skr_mint:
                logger.warning("[{}] SKR mint not configured", self.account_id)
                return self.strategy.get("default_swap_size", 0.1)

            try:
                balance = await self.solana_client.get_token_balance(
                    Pubkey.from_string(str(self.keypair.pubkey())),
                    Pubkey.from_string(skr_mint)
                )
                
                if balance is None or balance == 0:
                    logger.warning("[{}] No SKR balance to sell", self.account_id)
                    return None

                # Convert from lamports to tokens (6 decimals for SKR)
                amount = balance / 1e6
                logger.info("[{}] Using entire SKR balance: {}", self.account_id, amount)
                return amount

            except Exception as e:
                logger.error("[{}] Failed to get SKR balance: {}", self.account_id, e)
                return self.strategy.get("default_swap_size", 0.1)

        elif action == "BUY":
            # Determine target swap amount
            if self.last_swap_output_amount is not None:
                target_amount = self.last_swap_output_amount
                logger.info(
                    "[{}] Using saved SOL amount from last SELL: {}",
                    self.account_id,
                    target_amount
                )
            else:
                # First BUY or no previous SELL
                target_amount = self.strategy.get("default_swap_size", 0.1)
                logger.info(
                    "[{}] No previous SELL amount, using default: {}",
                    self.account_id,
                    target_amount
                )

            # Check available SOL balance
            if not self.solana_client or not self.keypair:
                logger.warning("[{}] Cannot check SOL balance: missing client/keypair", self.account_id)
                return target_amount

            try:
                sol_balance = await self.solana_client.get_balance(
                    Pubkey.from_string(str(self.keypair.pubkey()))
                )

                if sol_balance is None:
                    logger.warning("[{}] Failed to get SOL balance", self.account_id)
                    return target_amount

                # Convert lamports to SOL
                sol_balance_tokens = sol_balance / 1e9
                # Reserve for fees
                min_reserve = self.strategy.get("min_sol_reserve", 0.01)
                available_sol = sol_balance_tokens - min_reserve

                logger.info(
                    "[{}] SOL balance: {} (available: {} after {} reserve)",
                    self.account_id,
                    sol_balance_tokens,
                    available_sol,
                    min_reserve
                )

                if available_sol <= 0:
                    logger.warning("[{}] Insufficient SOL balance for swap", self.account_id)
                    return None

                # Use lesser of target amount or available balance
                swap_amount = min(target_amount, available_sol)
                if swap_amount < target_amount:
                    logger.warning(
                        "[{}] Reducing swap from {} to {} SOL (insufficient balance)",
                        self.account_id,
                        target_amount,
                        swap_amount
                    )

                return swap_amount

            except Exception as e:
                logger.error("[{}] Failed to check SOL balance: {}", self.account_id, e)
                return target_amount

        return None

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
