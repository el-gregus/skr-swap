"""Signal routing to wallet accounts."""
from typing import TYPE_CHECKING
from loguru import logger

from models.schemas import Signal

if TYPE_CHECKING:
    from services.account_manager import AccountManager
    from services.analytics_store import AnalyticsStore


class SignalRouter:
    """Routes trading signals to appropriate wallet accounts."""

    def __init__(self, account_manager: "AccountManager", analytics: "AnalyticsStore"):
        self.account_manager = account_manager
        self.analytics = analytics

    async def handle(self, signal: Signal) -> None:
        """
        Route signal to all enabled accounts that match the symbol.

        Args:
            signal: Parsed trading signal
        """
        logger.info("Routing signal: {} {}", signal.action, signal.symbol)

        # Record signal in database
        self.analytics.record_signal(
            action=signal.action,
            symbol=signal.symbol,
            amount=signal.amount,
            price=signal.price,
            note=signal.note,
            payload=signal.metadata,
        )

        # Route to matching accounts
        routed = 0
        for account in self.account_manager.accounts.values():
            if not account.enabled:
                continue

            # Check if account trades this symbol
            strategy = account.strategy
            token_pair = strategy.get("token_pair", "")

            if token_pair == signal.symbol:
                await account.swap_engine.process_signal(signal)
                routed += 1

        if routed == 0:
            logger.warning("No accounts matched signal symbol: {}", signal.symbol)
        else:
            logger.info("Signal routed to {} account(s)", routed)
