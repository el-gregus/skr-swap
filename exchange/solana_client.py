"""Solana RPC client wrapper."""
from typing import Optional
import base64
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders import message
from solders.signature import Signature
from loguru import logger


class SolanaClient:
    """Wrapper for Solana RPC client."""

    def __init__(self, rpc_url: str, commitment: str = "confirmed"):
        self.rpc_url = rpc_url
        self.commitment = commitment
        self.client = AsyncClient(rpc_url, commitment=Confirmed)

    async def close(self):
        """Close the RPC client."""
        await self.client.close()

    async def get_balance(self, pubkey: Pubkey) -> Optional[int]:
        """
        Get SOL balance for a wallet in lamports.

        Args:
            pubkey: Wallet public key

        Returns:
            Balance in lamports or None if failed
        """
        try:
            response = await self.client.get_balance(pubkey)
            if response.value is not None:
                return response.value
            return None
        except Exception as e:
            logger.error("Failed to get balance: {}", e)
            return None

    async def get_token_balance(
        self,
        owner: Pubkey,
        mint: Pubkey,
    ) -> Optional[int]:
        """
        Get token balance for a wallet.

        Args:
            owner: Wallet public key
            mint: Token mint address

        Returns:
            Balance in base units or None if failed
        """
        try:
            from solana.rpc.types import TokenAccountOpts

            # Get token accounts by owner
            opts = TokenAccountOpts(mint=mint)
            response = await self.client.get_token_accounts_by_owner(
                owner,
                opts
            )

            if not response.value or len(response.value) == 0:
                return 0

            # Get balance from first token account
            token_account = response.value[0].pubkey
            balance_response = await self.client.get_token_account_balance(token_account)

            if balance_response.value:
                return int(balance_response.value.amount)

            return 0

        except Exception as e:
            import traceback
            logger.error("Failed to get token balance: {} | Type: {} | Traceback: {}",
                        str(e) if str(e) else repr(e),
                        type(e).__name__,
                        traceback.format_exc())
            return None

    async def send_transaction(
        self,
        transaction_base64: str,
        keypair: Keypair,
    ) -> Optional[str]:
        """
        Sign and send a transaction.

        Args:
            transaction_base64: Base64-encoded transaction from Jupiter
            keypair: Wallet keypair for signing

        Returns:
            Transaction signature or None if failed
        """
        try:
            # Decode transaction
            tx_bytes = base64.b64decode(transaction_base64)
            transaction = VersionedTransaction.from_bytes(tx_bytes)

            # Sign transaction by passing keypair to constructor
            message = transaction.message
            signed_tx = VersionedTransaction(message, [keypair])

            # Send transaction
            response = await self.client.send_transaction(signed_tx)

            if response.value:
                signature = str(response.value)
                logger.info("Transaction sent: {}", signature)
                return signature

            return None

        except Exception as e:
            logger.error("Failed to send transaction: {}", e)
            return None

    async def confirm_transaction(
        self,
        signature: str,
        max_retries: int = 30,
    ) -> bool:
        """
        Wait for transaction confirmation.

        Args:
            signature: Transaction signature
            max_retries: Maximum confirmation attempts

        Returns:
            True if confirmed, False otherwise
        """
        try:
            sig = Signature.from_string(signature)
            response = await self.client.confirm_transaction(
                sig,
                commitment=Confirmed,
            )

            if response.value:
                logger.info("Transaction confirmed: {}", signature)
                return True

            return False

        except Exception as e:
            logger.error("Failed to confirm transaction: {}", e)
            return False
