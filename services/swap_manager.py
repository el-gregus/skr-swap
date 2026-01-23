"""Swap execution manager for Jupiter swaps."""
from typing import Dict, Any
from loguru import logger

from models.schemas import SwapRequest, SwapResult
from exchange.jupiter_client import JupiterClient
from exchange.solana_client import SolanaClient
from services.analytics_store import AnalyticsStore
from utils.wallet import to_lamports, format_lamports
from solders.keypair import Keypair
from solders.pubkey import Pubkey


class SwapManager:
    """Manages swap execution through Jupiter."""

    def __init__(
        self,
        account_id: str,
        account_label: str,
        keypair: Keypair,
        jupiter: JupiterClient,
        solana: SolanaClient,
        analytics: AnalyticsStore,
        token_mints: Dict[str, str],
        config: Dict[str, Any],
    ):
        self.account_id = account_id
        self.account_label = account_label
        self.keypair = keypair
        self.jupiter = jupiter
        self.solana = solana
        self.analytics = analytics
        self.token_mints = token_mints
        self.config = config

    async def execute_swap(self, request: SwapRequest) -> SwapResult:
        """
        Execute a token swap through Jupiter.

        Args:
            request: Swap request details

        Returns:
            SwapResult with execution details
        """
        # Get token mints
        input_mint = self.token_mints.get(request.input_token)
        output_mint = self.token_mints.get(request.output_token)

        if not input_mint or not output_mint:
            error = f"Unknown token: {request.input_token} or {request.output_token}"
            logger.error("[{}] {}", self.account_id, error)
            return SwapResult(success=False, input_amount=request.amount, error=error)

        input_decimals = await self._get_token_decimals(request.input_token, input_mint)
        output_decimals = await self._get_token_decimals(request.output_token, output_mint)

        # Convert amount to lamports
        input_lamports = to_lamports(request.amount, decimals=input_decimals)

        # Fetch current USD prices for input/output tokens
        input_token_usd_price = None
        input_usd = None
        try:
            token_mints = [input_mint, output_mint]
            prices = await self.jupiter.get_token_price(token_mints)
            if prices:
                input_token_usd_price = prices.get(input_mint, 0)
                input_usd = request.amount * input_token_usd_price if input_token_usd_price else None
        except Exception as e:
            logger.warning("[{}] Failed to fetch USD prices: {}", self.account_id, e)

        # Create swap record with USD prices
        swap_id = self.analytics.create_swap(
            account_id=self.account_id,
            account_label=self.account_label,
            input_token=request.input_token,
            output_token=request.output_token,
            input_amount=request.amount,
            meta={"slippage_bps": request.slippage_bps},
            input_token_usd_price=input_token_usd_price,
            input_usd=input_usd,
        )

        try:
            # Get quote from Jupiter
            logger.debug("[{}] Fetching Jupiter quote...", self.account_id)
            quote = await self.jupiter.get_quote(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=input_lamports,
                slippage_bps=request.slippage_bps,
            )

            if not quote:
                raise Exception("Failed to get quote from Jupiter")

            # Get swap transaction
            logger.debug("[{}] Getting swap transaction...", self.account_id)
            compute_unit_price = self.config.get("jupiter", {}).get("compute_unit_price", 100000)

            swap_tx = await self.jupiter.get_swap_transaction(
                quote=quote,
                user_public_key=str(self.keypair.pubkey()),
                compute_unit_price_micro_lamports=compute_unit_price,
            )

            if not swap_tx:
                raise Exception("Failed to get swap transaction from Jupiter")

            # Sign and send transaction
            logger.debug("[{}] Signing and sending transaction...", self.account_id)
            tx_base64 = swap_tx.get("swapTransaction")
            if not tx_base64:
                raise Exception("No transaction in Jupiter response")

            signature = await self.solana.send_transaction(tx_base64, self.keypair)
            if not signature:
                raise Exception("Failed to send transaction")

            # Wait for confirmation
            logger.debug("[{}] Waiting for confirmation...", self.account_id)
            confirmed = await self.solana.confirm_transaction(signature)
            if not confirmed:
                logger.warning("[{}] Transaction sent but confirmation failed: {}", self.account_id, signature)

            # Fetch transaction fee (lamports)
            fee_lamports = await self.solana.get_transaction_fee(signature)
            fee_usd = None

            # Calculate output amount and price
            output_lamports = int(quote.get("outAmount", 0))
            output_amount = format_lamports(output_lamports, decimals=output_decimals)
            price = output_amount / request.amount if request.amount > 0 else 0

            # Fetch output token USD price
            output_token_usd_price = None
            output_usd = None
            try:
                prices = await self.jupiter.get_token_price([output_mint])
                if prices:
                    output_token_usd_price = prices.get(output_mint, 0)
                    output_usd = output_amount * output_token_usd_price if output_token_usd_price else None
            except Exception as e:
                logger.warning("[{}] Failed to fetch output USD price: {}", self.account_id, e)

            # Calculate fee USD if possible (fees are in SOL)
            if fee_lamports is not None:
                fee_sol = format_lamports(fee_lamports, decimals=9)
                sol_usd_price = None
                if request.input_token.upper() == "SOL":
                    sol_usd_price = input_token_usd_price
                elif request.output_token.upper() == "SOL":
                    sol_usd_price = output_token_usd_price
                else:
                    try:
                        sol_mint = self.token_mints.get("SOL")
                        if sol_mint:
                            sol_prices = await self.jupiter.get_token_price([sol_mint])
                            if sol_prices:
                                sol_usd_price = sol_prices.get(sol_mint, 0)
                    except Exception as e:
                        logger.warning("[{}] Failed to fetch SOL USD price for fees: {}", self.account_id, e)
                if sol_usd_price:
                    fee_usd = fee_sol * sol_usd_price

            # Mark swap as completed with USD prices
            self.analytics.complete_swap(
                swap_id=swap_id,
                signature=signature,
                output_amount=output_amount,
                price=price,
                slippage=float(quote.get("priceImpactPct", 0)),
                output_token_usd_price=output_token_usd_price,
                output_usd=output_usd,
                fee_lamports=fee_lamports,
                fee_usd=fee_usd,
            )

            logger.info(
                "[{}] Swap completed: {} {} → {} {} (price: {:.6f})",
                self.account_id,
                request.amount,
                request.input_token,
                output_amount,
                request.output_token,
                price,
            )

            return SwapResult(
                success=True,
                signature=signature,
                input_amount=request.amount,
                output_amount=output_amount,
                price=price,
                slippage=float(quote.get("priceImpactPct", 0)),
            )

        except Exception as e:
            error_msg = str(e)
            logger.error("[{}] Swap failed: {}", self.account_id, error_msg)

            # Mark swap as failed
            self.analytics.fail_swap(swap_id, error_msg)

            return SwapResult(
                success=False,
                input_amount=request.amount,
                error=error_msg,
            )

    async def _get_token_decimals(self, symbol: str, mint: str) -> int:
        """Resolve token decimals with SOL + fallback handling."""
        if symbol.upper() == "SOL":
            return 9

        try:
            decimals = await self.solana.get_token_decimals(Pubkey.from_string(mint))
            if decimals is not None:
                return int(decimals)
        except Exception as e:
            logger.warning("[{}] Failed to get decimals for {}: {}", self.account_id, symbol, e)

        return 6
