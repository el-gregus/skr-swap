"""Jupiter aggregator API client for Solana token swaps."""
from typing import Optional, Dict, Any
import httpx
from loguru import logger


class JupiterClient:
    """Client for Jupiter swap aggregator API."""

    def __init__(self, api_url: str = "https://quote-api.jup.ag/v6", api_key: Optional[str] = None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

        # Set up headers with API key if provided
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key

        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a swap quote from Jupiter.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Input amount in lamports/base units
            slippage_bps: Slippage tolerance in basis points (50 = 0.5%)

        Returns:
            Quote dictionary or None if failed
        """
        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(slippage_bps),
            }

            response = await self.client.get(f"{self.api_url}/quote", params=params)
            response.raise_for_status()

            quote = response.json()
            logger.info(
                "Jupiter quote: {} {} → {} {} (price impact: {}%)",
                amount,
                input_mint[:8],
                quote.get("outAmount", "?"),
                output_mint[:8],
                quote.get("priceImpactPct", 0),
            )
            return quote

        except httpx.HTTPError as e:
            logger.error("Failed to fetch Jupiter quote: {}", e)
            return None
        except Exception as e:
            logger.error("Unexpected error fetching quote: {}", e)
            return None

    async def get_swap_transaction(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        compute_unit_price_micro_lamports: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a swap transaction from Jupiter based on a quote.

        Args:
            quote: Quote object from get_quote()
            user_public_key: User's wallet public key (base58)
            wrap_unwrap_sol: Automatically wrap/unwrap SOL
            compute_unit_price_micro_lamports: Priority fee

        Returns:
            Swap transaction data or None if failed
        """
        try:
            payload = {
                "quoteResponse": quote,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": wrap_unwrap_sol,
            }

            if compute_unit_price_micro_lamports:
                payload["prioritizationFeeLamports"] = {
                    "priorityLevelWithMaxLamports": {
                        "maxLamports": compute_unit_price_micro_lamports,
                        "priorityLevel": "high"
                    }
                }

            response = await self.client.post(
                f"{self.api_url}/swap",
                json=payload,
            )
            response.raise_for_status()

            swap_data = response.json()
            logger.debug("Received swap transaction from Jupiter")
            return swap_data

        except httpx.HTTPError as e:
            logger.error("Failed to get swap transaction: {}", e)
            return None
        except Exception as e:
            logger.error("Unexpected error getting swap transaction: {}", e)
            return None

    async def get_token_price(
        self,
        token_ids: list[str],
        vs_token: str = "USDC"  # Changed to USDC as that's what V3 uses
    ) -> Optional[Dict[str, float]]:
        """
        Get token prices from Jupiter Price API V3.

        Args:
            token_ids: List of token mint addresses
            vs_token: Base token to price against (default: USDC for USD prices)

        Returns:
            Dictionary of {mint: price in USD} or None if failed
        """
        if not self.api_key:
            logger.warning("Jupiter API key not configured, skipping price fetch")
            return None

        try:
            params = {
                "ids": ",".join(token_ids),
            }

            # Use V3 API endpoint (requires API key)
            response = await self.client.get(
                "https://api.jup.ag/price/v3",
                params=params
            )
            response.raise_for_status()

            data = response.json()
            prices = {}

            # V3 format: {"mint": {"usdPrice": 0.123, ...}, ...}
            # Response is a flat dict with mints as keys (no "data" wrapper)
            for mint, info in data.items():
                if isinstance(info, dict):
                    price_val = info.get("usdPrice")
                    if price_val is not None:
                        prices[mint] = float(price_val)

            logger.debug("Fetched prices for {} tokens", len(prices))
            return prices

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Jupiter API key is invalid or not authorized")
            else:
                logger.error("Failed to fetch token prices: HTTP {}", e.response.status_code)
            return None
        except Exception as e:
            logger.error("Failed to fetch token prices: {}", str(e))
            return None
