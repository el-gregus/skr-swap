"""SKR Swap Bot - Solana token swap bot powered by Jupiter."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import load_config
from utils.logging import setup_logging
from webhooks.tradingview import router as webhook_router
from services.dashboard_router import router as dashboard_router
from services.analytics_store import AnalyticsStore
from services.signal_router import SignalRouter
from services.account_manager import AccountManager
from exchange.jupiter_client import JupiterClient
from exchange.solana_client import SolanaClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting SKR Swap Bot...")

    # Clean up old price data
    analytics = app.state.analytics
    removed = analytics.cleanup_old_prices(days=7)
    if removed:
        logger.info("Cleaned up {} old price records", removed)

    yield

    # Shutdown
    logger.info("Shutting down SKR Swap Bot...")

    # Close clients
    if hasattr(app.state, "jupiter"):
        await app.state.jupiter.close()
    if hasattr(app.state, "solana"):
        await app.state.solana.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Load configuration
    config = load_config()

    # Setup logging
    log_config = config.get("logging", {})
    setup_logging(
        log_dir=log_config.get("dir", "./logs"),
        level=log_config.get("level", "INFO"),
    )

    logger.info("Configuration loaded")

    # Initialize database
    analytics = AnalyticsStore(db_path="./data/skr_swap.db")
    logger.info("Analytics database initialized")

    # Initialize Jupiter client
    jupiter_config = config.get("jupiter", {})
    jupiter = JupiterClient(
        api_url=jupiter_config.get("api_url", "https://quote-api.jup.ag/v6"),
        api_key=jupiter_config.get("api_key")
    )
    logger.info("Jupiter client initialized")

    # Initialize Solana client
    solana_config = config.get("solana", {})
    solana = SolanaClient(
        rpc_url=solana_config.get("rpc_url", "https://api.mainnet-beta.solana.com"),
        commitment=solana_config.get("commitment", "confirmed"),
    )
    logger.info("Solana RPC client initialized")

    # Initialize account manager
    account_manager = AccountManager(
        config=config,
        jupiter=jupiter,
        solana=solana,
        analytics=analytics,
    )

    # Initialize signal router
    signal_router = SignalRouter(
        account_manager=account_manager,
        analytics=analytics,
    )

    # Create FastAPI app
    app = FastAPI(
        title="SKR Swap Bot",
        description="Solana token swap bot powered by Jupiter",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store state
    app.state.config = config
    app.state.analytics = analytics
    app.state.jupiter = jupiter
    app.state.solana = solana
    app.state.account_manager = account_manager
    app.state.signal_router = signal_router

    # Include routers
    app.include_router(webhook_router, tags=["webhooks"])
    app.include_router(dashboard_router, tags=["dashboard"])

    logger.info("SKR Swap Bot initialized")

    return app


# Create app instance
app = create_app()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "skr-swap",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )
