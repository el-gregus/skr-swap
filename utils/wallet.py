"""Wallet utilities for Solana."""
from typing import Optional
import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey


def load_keypair_from_base58(private_key: str) -> Optional[Keypair]:
    """
    Load a Keypair from a base58-encoded private key string.

    Args:
        private_key: Base58-encoded private key (58-88 characters)

    Returns:
        Keypair object or None if invalid
    """
    try:
        decoded = base58.b58decode(private_key)
        # Solana private keys are 64 bytes (32 secret + 32 public)
        if len(decoded) == 64:
            return Keypair.from_bytes(decoded)
        # Some wallets export just the 32-byte seed
        elif len(decoded) == 32:
            return Keypair.from_seed(decoded)
        else:
            return None
    except Exception:
        return None


def pubkey_from_string(address: str) -> Optional[Pubkey]:
    """
    Parse a public key from a base58 address string.

    Args:
        address: Base58-encoded Solana address

    Returns:
        Pubkey object or None if invalid
    """
    try:
        return Pubkey.from_string(address)
    except Exception:
        return None


def format_lamports(lamports: int, decimals: int = 9) -> float:
    """
    Convert lamports to human-readable decimal amount.

    Args:
        lamports: Amount in base units
        decimals: Token decimals (9 for SOL, 6 for USDC, etc.)

    Returns:
        Decimal amount as float
    """
    return lamports / (10 ** decimals)


def to_lamports(amount: float, decimals: int = 9) -> int:
    """
    Convert decimal amount to lamports.

    Args:
        amount: Decimal amount
        decimals: Token decimals

    Returns:
        Amount in base units (lamports)
    """
    return int(amount * (10 ** decimals))
