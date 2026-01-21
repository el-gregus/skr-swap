"""Logging configuration for SKR Swap bot."""
import sys
from pathlib import Path
from loguru import logger


def setup_logging(log_dir: str = "./logs", level: str = "INFO") -> None:
    """Configure loguru logging with file and console output."""
    # Remove default handler
    logger.remove()

    # Console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # File handler
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path / "skr-swap.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
    )

    logger.info(f"Logging configured at {level} level")
