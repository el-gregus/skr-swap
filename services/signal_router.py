"""Signal routing to wallet accounts."""
from typing import TYPE_CHECKING, Dict, Tuple, Any
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
        self.sequence_state: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def _normalize_signal_type(self, signal_type: str) -> str:
        normalized = str(signal_type).strip().lower()
        normalized = normalized.replace("_", "-").replace(" ", "-")
        if normalized in {"mr-0.5", "mrlow"}:
            return "mr-low"
        return normalized

    def _should_execute_sequence(self, account_id: str, signal: Signal) -> bool:
        signal_type = signal.metadata.get("signal_type")
        if not signal_type:
            logger.info(
                "[{}] Missing signal_type metadata; ignoring legacy signal",
                account_id,
            )
            return False

        signal_type = self._normalize_signal_type(signal_type)
        key = (account_id, signal.symbol)
        state = self.sequence_state.get(key)

        if signal_type == "mr-low":
            if state and state.get("action") != signal.action:
                logger.info(
                    "[{}] MR-Low opposite direction; resetting sequence for {}",
                    account_id,
                    signal.symbol,
                )
            self.sequence_state[key] = {"stage": "mr_low", "action": signal.action}
            logger.info(
                "[{}] MR-Low received; waiting for Mean ({})",
                account_id,
                signal.action,
            )
            return False

        if signal_type == "mean":
            if not state or state.get("stage") != "mr_low" or state.get("action") != signal.action:
                logger.info(
                    "[{}] Mean ignored; no MR-Low sequence for {} {}",
                    account_id,
                    signal.action,
                    signal.symbol,
                )
                return False
            state["stage"] = "mean"
            logger.info(
                "[{}] Mean received; waiting for Conf/Trend ({})",
                account_id,
                signal.action,
            )
            return False

        if signal_type in {"conf", "trend"}:
            if state and state.get("stage") == "mean" and state.get("action") == signal.action:
                self.sequence_state.pop(key, None)
                logger.info(
                    "[{}] {} received; sequence complete for {}",
                    account_id,
                    signal_type,
                    signal.symbol,
                )
                return True
            logger.info(
                "[{}] {} ignored; sequence incomplete for {} {}",
                account_id,
                signal_type,
                signal.action,
                signal.symbol,
            )
            return False

        logger.info(
            "[{}] Unrecognized signal type {}; ignoring",
            account_id,
            signal_type,
        )
        return False

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
                if self._should_execute_sequence(account.id, signal):
                    await account.swap_engine.process_signal(signal)
                routed += 1

        if routed == 0:
            logger.warning("No accounts matched signal symbol: {}", signal.symbol)
        else:
            logger.info("Signal routed to {} account(s)", routed)
