"""Jupiter aggregator API client for Solana token swaps."""
from typing import Optional, Dict, Any
import httpx
from loguru import logger


class JupiterClient:
    """Client for Jupiter swap aggregator API."""

    def __init__(self, api_url: str = "https://quote-api.jup.ag/v6"):
        self.api_url = api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

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
        vs_token: str = "So11111111111111111111111111111111111111112"  # SOL
    ) -> Optional[Dict[str, float]]:
        """
        Get token prices from Jupiter Price API.

        Args:
            token_ids: List of token mint addresses
            vs_token: Base token to price against (default: SOL)

        Returns:
            Dictionary of {mint: price} or None if failed
        """
        try:
            params = {
                "ids": ",".join(token_ids),
                "vsToken": vs_token,
            }

            response = await self.client.get(
                "https://price.jup.ag/v4/price",
                params=params
            )
            response.raise_for_status()

            data = response.json()
            prices = {}
            for mint, info in data.get("data", {}).items():
                prices[mint] = float(info.get("price", 0))

            return prices

        except Exception as e:
            logger.error("Failed to fetch token prices: {}", e)
            return None
