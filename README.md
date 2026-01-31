# SKR Swap Bot

A Solana-based cryptocurrency swap bot that receives trading signals via webhooks and executes token swaps through Jupiter aggregator.

## Features

- 🔄 **Automated Swapping**: Execute SOL ↔ SKR swaps based on TradingView signals
- 🚀 **Jupiter Integration**: Best swap rates through Jupiter aggregator
- 📊 **Dashboard**: Real-time monitoring of swaps and signals
- 💾 **Analytics**: SQLite persistence for all swaps and signals
- 🔐 **Secure**: Private keys never logged or exposed
- ⚡ **Fast**: Optimized transaction execution with priority fees

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.sample .env
cp config.sample.yaml config.yaml

# Edit .env and config.yaml with your settings
# IMPORTANT: Add your wallet private key to .env

# Run
uvicorn main:app --host 0.0.0.0 --port 4201 --reload
```

## Configuration

### Environment Variables (.env)

```bash
WALLET_PRIVATE_KEY=your_base58_private_key
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
JUPITER_API_URL=https://quote-api.jup.ag/v6
LOG_LEVEL=INFO
```

### Config File (config.yaml)

See `config.sample.yaml` for a full example with comments.

Key settings:
- `tokens`: Token mint addresses (SOL, SKR, USDC, etc.)
- `accounts`: Wallet configurations with strategies
- `jupiter`: Jupiter API settings and priority fees
- `risk`: Global risk limits and safety parameters

## Usage

### Send a Swap Signal

```bash
# JSON format
curl -X POST http://localhost:4201/webhook \
  -H "Content-Type: application/json" \
  -d '{"action":"BUY","symbol":"SKR-USDC","amount":10.0}'

# CSV format (TradingView compatible)
curl -X POST http://localhost:4201/webhook \
  -H "Content-Type: text/plain" \
  --data-raw "action=BUY,symbol=SKR-USDC,amount=10.0"
```

### View Dashboard

Open http://localhost:4201 in your browser to see:
- Recent swaps with status
- Signal history
- Account balances (coming soon)

## Architecture

```
┌─────────────┐
│  TradingView│
│   Webhook   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│           FastAPI Application           │
│  ┌─────────────────────────────────┐   │
│  │   Signal Router                 │   │
│  └────────┬────────────────────────┘   │
│           │                             │
│           ▼                             │
│  ┌─────────────────────────────────┐   │
│  │   Account Manager               │   │
│  │  ┌──────────────────────────┐   │   │
│  │  │  Wallet Account 1        │   │   │
│  │  │  ├─ Swap Engine          │   │   │
│  │  │  └─ Swap Manager         │   │   │
│  │  └──────────────────────────┘   │   │
│  └─────────────────────────────────┘   │
│           │                             │
│           ▼                             │
│  ┌─────────────────────────────────┐   │
│  │   Jupiter Client                │   │
│  └────────┬────────────────────────┘   │
│           │                             │
│           ▼                             │
│  ┌─────────────────────────────────┐   │
│  │   Solana Client                 │   │
│  └────────┬────────────────────────┘   │
└───────────┼─────────────────────────────┘
            │
            ▼
    ┌───────────────┐
    │Solana Mainnet │
    └───────────────┘
```

## Safety Features

- ✅ Minimum SOL balance reserved for fees
- ✅ Maximum swap size limits
- ✅ Slippage protection
- ✅ Cooldown periods between swaps
- ✅ Balance validation before execution
- ✅ Transaction confirmation monitoring

## Development

See [CLAUDE.md](CLAUDE.md) for comprehensive development documentation including:
- Architecture details
- API integration guides
- Testing strategies
- Deployment checklist
- Common issues and solutions

## Production Deployment

1. Use a reliable RPC endpoint (Helius, Quicknode, etc.)
2. Fund wallet with SOL for transaction fees
3. Start with small test amounts
4. Monitor gas usage and optimize
5. Set up alerts for failed swaps
6. Never commit private keys to git

## Support

- Logs: `./logs/skr-swap.log`
- Database: `./data/skr_swap.db`
- Explorer: [Solana Explorer](https://explorer.solana.com/)

## License

MIT License - see LICENSE file for details

## Disclaimer

This software is for educational purposes. Use at your own risk. Always test with small amounts first.
