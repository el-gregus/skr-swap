"""Manages multiple wallet accounts for swap execution."""
from typing import Dict, Any
from dataclasses import dataclass
from loguru import logger

from utils.wallet import load_keypair_from_base58
from exchange.jupiter_client import JupiterClient
from exchange.solana_client import SolanaClient
from services.analytics_store import AnalyticsStore
from services.swap_manager import SwapManager
from services.swap_engine import SwapEngine
from solders.keypair import Keypair


@dataclass
class WalletAccount:
    """Represents a wallet account with swap capabilities."""
    id: str
    label: str
    enabled: bool
    keypair: Keypair
    strategy: Dict[str, Any]
    swap_manager: SwapManager
    swap_engine: SwapEngine


class AccountManager:
    """Manages multiple wallet accounts."""

    def __init__(
        self,
        config: Dict[str, Any],
        jupiter: JupiterClient,
        solana: SolanaClient,
        analytics: AnalyticsStore,
    ):
        self.config = config
        self.jupiter = jupiter
        self.solana = solana
        self.analytics = analytics
        self.accounts: Dict[str, WalletAccount] = {}

        self._build_accounts()

    def _build_accounts(self) -> None:
        """Build wallet accounts from configuration."""
        accounts_config = self.config.get("accounts", [])
        token_mints = self.config.get("tokens", {})

        for account_config in accounts_config:
            account_id = account_config.get("id")
            if not account_id:
                logger.warning("Account config missing ID, skipping")
                continue

            # Load keypair
            private_key = account_config.get("private_key", "")
            if not private_key:
                logger.warning("Account {} missing private key, skipping", account_id)
                continue

            keypair = load_keypair_from_base58(private_key)
            if not keypair:
                logger.error("Account {} has invalid private key, skipping", account_id)
                continue

            # Create swap manager
            swap_manager = SwapManager(
                account_id=account_id,
                account_label=account_config.get("label", account_id),
                keypair=keypair,
                jupiter=self.jupiter,
                solana=self.solana,
                analytics=self.analytics,
                token_mints=token_mints,
                config=self.config,
            )

            # Create swap engine
            swap_engine = SwapEngine(
                account_id=account_id,
                account_label=account_config.get("label", account_id),
                strategy=account_config.get("strategy", {}),
                analytics=self.analytics,
                swap_manager=swap_manager,
            )

            # Create account
            account = WalletAccount(
                id=account_id,
                label=account_config.get("label", account_id),
                enabled=account_config.get("enabled", True),
                keypair=keypair,
                strategy=account_config.get("strategy", {}),
                swap_manager=swap_manager,
                swap_engine=swap_engine,
            )

            self.accounts[account_id] = account

            logger.info(
                "Account '{}' [{}] initialized (address: {})",
                account.label,
                account.id,
                str(keypair.pubkey())[:16] + "..."
            )

        logger.info("Initialized {} wallet account(s)", len(self.accounts))

    def get_account(self, account_id: str) -> WalletAccount | None:
        """Get account by ID."""
        return self.accounts.get(account_id)
