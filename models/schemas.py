"""Pydantic models for SKR Swap bot."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class Signal(BaseModel):
    """Trading signal from webhook."""
    action: str  # BUY or SELL
    symbol: str  # e.g., "SOL-SKR"
    amount: Optional[float] = None
    price: Optional[float] = None
    timestamp: Optional[datetime] = None
    note: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SwapRequest(BaseModel):
    """Request to execute a token swap."""
    account_id: str
    input_token: str  # e.g., "SOL"
    output_token: str  # e.g., "SKR"
    amount: float  # Amount of input token
    slippage_bps: int = 50  # 0.5% default


class SwapResult(BaseModel):
    """Result of a swap execution."""
    success: bool
    signature: Optional[str] = None  # Solana transaction signature
    input_amount: float
    output_amount: Optional[float] = None
    price: Optional[float] = None  # Execution price
    slippage: Optional[float] = None  # Actual slippage
    error: Optional[str] = None


class TokenBalance(BaseModel):
    """Token balance for an account."""
    token: str  # e.g., "SOL"
    mint: str  # Token mint address
    balance: float
    decimals: int = 9
    lamports: int


class AccountConfig(BaseModel):
    """Configuration for a wallet account."""
    id: str
    label: str
    enabled: bool = True
    private_key: str
    strategy: Dict[str, Any]


class JupiterQuote(BaseModel):
    """Jupiter swap quote."""
    input_mint: str
    output_mint: str
    in_amount: int  # Lamports
    out_amount: int  # Lamports
    price_impact_pct: float
    route_plan: list
    slippage_bps: int
