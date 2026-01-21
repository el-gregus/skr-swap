# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SKR Swap is a Solana-based cryptocurrency swap bot that receives trading signals via FastAPI webhooks (primarily from TradingView) and executes token swaps through Jupiter aggregator. It's built on a similar architecture to perp-bot but adapted for spot token swapping instead of perpetual futures trading.

The bot manages multiple wallet accounts, each capable of swapping between different token pairs. All swaps and signals are persisted to SQLite for analytics and dashboard display.

## Commands

### Development

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
cp config.sample.yaml config.yaml

# Run development server (hot-reload enabled)
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Testing Webhooks

```bash
# Test JSON webhook
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{"action":"BUY","symbol":"SOL-SKR","amount":1.0}'

# Test CSV payload (TradingView style)
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: text/plain" \
  --data-raw "action=SELL,symbol=SOL-SKR,amount=1.0"

# Test indicator format
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: text/plain" \
  --data-raw "SOL-SKR,30s,indicator,BUY,1737385200,142.35"
```

### Systemd Deployment

```bash
sudo cp systemd/skr-swap.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now skr-swap.service
journalctl -u skr-swap -f -n 100
```

## Architecture

### Core Data Flow

1. **Webhook Receipt** (`webhooks/tradingview.py`): Receives signals from external sources, parses JSON/CSV formats
2. **Signal Routing** (`services/signal_router.py`): Routes parsed signals to appropriate wallet accounts
3. **Account Management** (`services/account_manager.py`): Manages multiple wallet accounts, applies risk limits
4. **Swap Engine** (`services/swap_engine.py`): Implements swap logic and strategy rules
5. **Swap Execution** (`services/swap_manager.py`): Executes swaps through Jupiter API
6. **Jupiter Client** (`exchange/jupiter_client.py`): Jupiter aggregator API integration

### Multi-Account System

The `AccountManager` orchestrates multiple independent wallet accounts:
- Each account has its own wallet keypair and swap strategy
- Accounts can target different token pairs (e.g., SOL-SKR, SOL-USDC)
- Risk limits (max_swap_size, min_balance) apply per account
- The dashboard shows data from `dashboard.primary_account_id` in config

### Jupiter Integration

The Jupiter client (`exchange/jupiter_client.py`) provides:
- Quote fetching for best swap rates
- Swap transaction creation
- Slippage protection
- Token account management (ATA creation/lookup)

Key methods:
```python
async def get_quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Dict
async def execute_swap(quote: Dict, wallet: Keypair) -> str  # Returns transaction signature
async def get_token_balance(wallet: PublicKey, mint: str) -> float
```

### Strategy Engine

The `SwapEngine` implements signal-based trading logic:
- Receives BUY/SELL signals from webhooks
- Validates signals against current positions
- Applies strategy rules (e.g., cooldown periods, min/max swap sizes)
- Triggers swap execution via `SwapManager`

Strategy parameters (per account):
- `token_pair`: Trading pair (e.g., "SOL-SKR")
- `base_token`: Token to swap from (e.g., "SOL")
- `quote_token`: Token to swap to (e.g., "SKR")
- `default_swap_size`: Default amount to swap
- `max_slippage_bps`: Maximum slippage in basis points (100 = 1%)
- `min_time_between_swaps`: Cooldown period in seconds

### Token Configuration

Solana token mints are configured in `config.yaml`:
```yaml
tokens:
  SOL: So11111111111111111111111111111111111111112  # Native SOL
  SKR: <SKR_TOKEN_MINT_ADDRESS>
  USDC: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

### Analytics & Persistence

All data persists in SQLite (`./data/skr_swap.db`) via `AnalyticsStore`:
- **signals**: Every received indicator signal
- **swaps**: Full swap lifecycle (pending, completed, failed)
- **wallet_state**: Current token balances per account
- **price_ticks**: Recent price history for dashboard charts

Swap records track:
- Input/output tokens and amounts
- Execution price and slippage
- Transaction signature (for Solana Explorer links)
- Status (pending, completed, failed)
- Execution time

### Configuration Hierarchy

Settings load from `config.yaml` with environment variable overrides:
1. Load `config.yaml` (YAML structure)
2. Apply env overrides (e.g., `WALLET_PRIVATE_KEY`, `LOG_LEVEL`)
3. Build account list with wallet keypairs
4. Validate token mints and dashboard primary account

Key config sections:
- `tokens`: Token mint addresses (SOL, SKR, USDC, etc.)
- `accounts`: List of wallet accounts with private keys and strategies
- `jupiter`: Jupiter API configuration (URL, slippage, priority fees)
- `risk`: Global risk limits (max_swap_size, min_sol_balance)
- `webhook`: Authentication settings
- `logging`: Log level and directory
- `dashboard`: Primary account ID for dashboard display

### Wallet Management

Each account requires a Solana wallet:
- Private keys stored as base58-encoded strings in config (or env vars)
- Public keys (wallet addresses) derived from private keys
- Token accounts (ATAs) created automatically by Jupiter/Solana
- SOL balance maintained for transaction fees

**IMPORTANT**: Never commit private keys to git. Use `.env` for secrets.

### Transaction Execution

Swap execution flow:
1. `SwapEngine` receives signal and validates
2. `SwapManager` fetches quote from Jupiter
3. Jupiter returns optimal route and expected output
4. `SwapManager` creates and signs transaction
5. Transaction submitted to Solana RPC
6. Result recorded in database with signature

Transaction features:
- Compute unit price optimization (priority fees)
- Automatic retry logic for failed transactions
- Slippage protection
- Balance validation before execution

### Dashboard Integration

The dashboard router (`services/dashboard_router.py`) serves:
- Recent signals (filterable by token pair)
- Swap history (completed and failed)
- Account PnL summaries
- Current token balances
- Price charts (via Jupiter price API)

Data is scoped to `dashboard.primary_account_id` unless overridden via query params.

## File Structure

```
exchange/           # Exchange/DEX integrations
  jupiter_client.py # Jupiter aggregator API client
  solana_client.py  # Solana RPC client wrapper

services/           # Core business logic
  account_manager.py     # Multi-account orchestration
  signal_router.py       # Routes signals to accounts
  swap_engine.py         # Swap strategy logic
  swap_manager.py        # Swap execution wrapper
  analytics_store.py     # SQLite persistence layer
  dashboard_router.py    # Dashboard API endpoints

models/
  schemas.py        # Pydantic models (Signal, SwapRequest, etc.)

webhooks/
  tradingview.py    # Webhook parser and endpoint

utils/
  logging.py        # Loguru configuration
  wallet.py         # Wallet utilities (keypair loading, etc.)

main.py             # FastAPI app factory
config.py           # Settings loader with env override logic
```

## Important Patterns

### Wallet Security

- Private keys NEVER logged or exposed in API responses
- Use environment variables for production keys
- Implement key rotation strategy
- Store keys in secure vaults (not just .env files)

### Transaction Handling

When executing swaps:
1. Always validate sufficient balance before creating transaction
2. Set appropriate compute unit limits and priority fees
3. Implement retry logic with exponential backoff
4. Record transaction signatures for audit trail
5. Handle "transaction expired" gracefully

### Jupiter API Usage

Rate limiting considerations:
- Quote API: ~10 requests/second
- Swap API: Limited by Solana RPC capacity
- Use caching for frequently requested quotes
- Implement circuit breaker for API failures

### Error Recovery

Failed transactions should:
1. Record failure reason in database
2. Log full error context
3. NOT retry automatically (user should review)
4. Mark swap as "failed" status
5. Preserve all quote data for debugging

### Price Tracking

For dashboard charts:
- Use Jupiter Price API v2
- Store price ticks every 5-10 seconds
- Clean up old price data (keep 7 days)
- Calculate price changes (1h, 24h, 7d)

## Development Notes

- Python 3.11+ required (uses modern type hints)
- All timestamps internally use UTC
- Amounts stored as integers (lamports for SOL, base units for tokens)
- Logging via loguru (`utils/logging.py`)
- Database path: `./data/skr_swap.db` (WAL mode enabled)
- Sensitive fields masked in logs automatically

## Initial Implementation: SOL-SKR Swapping

The first version focuses on a single account swapping between SOL and SKR:
- Account: Single wallet with SOL and SKR balances
- Strategy: Signal-based (TradingView indicators trigger swaps)
- Pair: SOL ↔ SKR bidirectional swapping
- Execution: Jupiter aggregator for best rates
- Dashboard: Track swap history, current holdings, PnL

### Key Metrics

Dashboard displays:
- Current SOL balance
- Current SKR balance
- Total value (in SOL or USD)
- Swap count (24h, 7d, all-time)
- Win rate (profitable swaps / total swaps)
- Average slippage
- Gas fees spent

### Safety Features

- Minimum SOL balance (e.g., 0.1 SOL) reserved for fees
- Maximum swap size limits
- Slippage limits (reject if exceeded)
- Cooldown period between swaps
- Balance validation before execution

## Testing Strategy

### Unit Tests
- Signal parsing (various formats)
- Swap amount calculations
- Balance validation logic
- Quote selection (best route)

### Integration Tests
- Jupiter API calls (use devnet)
- Solana RPC interaction
- Webhook endpoint (mock TradingView)
- Database operations

### Manual Testing
- Execute small test swaps on devnet
- Verify transaction signatures on Solana Explorer
- Test dashboard with real data
- Validate slippage protection

## Deployment Checklist

Before production:
1. ✅ Configure mainnet RPC endpoint (Helius, Quicknode, etc.)
2. ✅ Fund wallet with SOL for gas fees
3. ✅ Set appropriate slippage limits (50-100 bps)
4. ✅ Configure priority fees for fast execution
5. ✅ Set up monitoring/alerts for failed swaps
6. ✅ Enable webhook authentication
7. ✅ Backup wallet private keys securely
8. ✅ Test with small amounts first
9. ✅ Monitor gas usage and optimize
10. ✅ Set up automatic balance alerts

## Common Issues

### "Insufficient liquidity"
- SKR is a new token with limited liquidity
- Reduce swap size or increase slippage tolerance
- Check Jupiter routes for available liquidity

### "Transaction failed"
- Solana congestion (adjust priority fees)
- Slippage exceeded (quote expired)
- Insufficient SOL for fees
- Token account not initialized

### "Account not found"
- Token account (ATA) doesn't exist
- Jupiter should create it automatically
- May need manual ATA creation for some tokens

## Roadmap

### Phase 1 (Current)
- [x] Basic SOL-SKR swapping
- [x] TradingView webhook integration
- [x] SQLite persistence
- [x] Simple dashboard

### Phase 2
- [ ] Multiple token pair support
- [ ] Advanced strategy rules (DCA, TWAP)
- [ ] Transaction priority optimization
- [ ] Enhanced analytics

### Phase 3
- [ ] Multi-wallet support
- [ ] Portfolio rebalancing
- [ ] Stop-loss / take-profit
- [ ] Telegram notifications

### Phase 4
- [ ] Limit orders (via Jupiter Limit Order)
- [ ] Cross-chain swaps
- [ ] MEV protection
- [ ] Advanced risk management

## Resources

- Jupiter API Docs: https://station.jup.ag/docs/apis/swap-api
- Solana Web3.js: https://solana-labs.github.io/solana-web3.js/
- Solana Explorer: https://explorer.solana.com/
- SKR Token: https://solana.com/solanamobile
- FastAPI Docs: https://fastapi.tiangolo.com/

## Support

For issues or questions:
- Check logs: `./logs/skr-swap.log`
- Verify config: `config.yaml`
- Test RPC: `solana cluster-version` (if using CLI)
- Review transactions: Solana Explorer + signature
