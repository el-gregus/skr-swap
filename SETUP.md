# SKR Swap Setup Guide

Quick setup guide to get the SKR Swap bot running.

## Prerequisites

- Python 3.11 or higher
- A Solana wallet with SOL for transaction fees
- (Optional) TradingView account for signals

## Step-by-Step Setup

### 1. Create Virtual Environment

```bash
cd ~/projects/skr-swap
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy sample files
cp .env.sample .env
cp config.sample.yaml config.yaml
```

### 4. Set Your Wallet Private Key

**IMPORTANT**: You need a Solana wallet with some SOL for transaction fees.

To get your private key from Phantom/Solflare:
1. Export your private key from your wallet
2. It should be a base58-encoded string (58-88 characters)
3. Add it to `.env`:

```bash
# Edit .env
WALLET_PRIVATE_KEY=your_base58_private_key_here
```

**NEVER commit .env to git!**

### 5. Update Token Addresses

Edit `config.yaml` and verify token mint addresses:

```yaml
tokens:
  SOL: So11111111111111111111111111111111111111112
  SKR: 2Ry8bbr959DhjUC2pW2TmqE97QQN5gwN1epb3kjfMy7g  # Verify this address
  USDC: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

**Note**: Verify the SKR token mint address is correct for mainnet.

### 6. Configure RPC Endpoint (Recommended)

For production, use a dedicated RPC endpoint:

```bash
# In .env
SOLANA_RPC_URL=https://your-rpc-endpoint.com

# Free options:
# - https://api.mainnet-beta.solana.com (rate limited)
# - https://api.helius.xyz (sign up for free tier)
# - https://rpc.ankr.com/solana (rate limited)
```

### 7. Start the Bot

```bash
# Development mode (with hot-reload)
uvicorn main:app --host 0.0.0.0 --port 4201 --reload

# Or use Python directly
python main.py
```

The bot will start on http://localhost:4201

### 8. Test the Setup

Open a new terminal and run:

```bash
# Test webhook
./test_webhook.sh

# Or manually test
curl -X POST http://localhost:4201/webhook \
  -H "Content-Type: application/json" \
  -d '{"action":"BUY","symbol":"SKR-USDC","amount":10.0}'
```

View the dashboard at: http://localhost:4201

## Verify Everything Works

1. ✅ Bot starts without errors
2. ✅ Dashboard loads (http://localhost:4201)
3. ✅ Webhook endpoint responds
4. ✅ Logs appear in `./logs/skr-swap.log`
5. ✅ Database created at `./data/skr_swap.db`

## Testing with Devnet (Recommended First)

Before using real funds, test on Solana devnet:

```bash
# In .env
SOLANA_RPC_URL=https://api.devnet.solana.com
```

You'll need:
- A devnet wallet
- Devnet SOL (get from https://faucet.solana.com/)
- Devnet token addresses (if testing token swaps)

## Production Checklist

Before going live with real funds:

- [ ] Use a reliable RPC endpoint (not free public RPCs)
- [ ] Fund wallet with sufficient SOL (at least 0.5 SOL recommended)
- [ ] Start with small test swaps (0.01-0.1 SOL)
- [ ] Monitor logs for errors
- [ ] Verify Jupiter quotes look reasonable
- [ ] Set appropriate slippage limits (50-100 bps)
- [ ] Configure risk limits in config.yaml
- [ ] Set up monitoring/alerts
- [ ] Backup wallet private keys securely
- [ ] NEVER share or commit private keys

## Common Issues

### "Failed to get quote from Jupiter"
- Check RPC endpoint is working
- Verify token mint addresses are correct
- Check network status (Solana mainnet)
- Try increasing timeout in config

### "Failed to send transaction"
- Insufficient SOL for fees (need ~0.001-0.01 SOL per transaction)
- Network congestion (increase priority fees)
- RPC rate limiting (upgrade RPC endpoint)

### "Account not found"
- Token account doesn't exist
- Jupiter should create it automatically
- May need manual ATA creation

### "Invalid private key"
- Check format (should be base58 encoded)
- Verify it's the full private key (not just seed phrase)
- Try exporting from wallet again

## Next Steps

Once running:

1. Monitor the logs: `tail -f logs/skr-swap.log`
2. View dashboard: http://localhost:4201
3. Send test signals via webhook
4. Check swaps execute correctly on Solana Explorer
5. Monitor gas usage and optimize

## Production Deployment

For systemd deployment on a server:

```bash
sudo cp systemd/skr-swap.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now skr-swap.service
journalctl -u skr-swap -f -n 100
```

## Getting Help

- Check logs: `./logs/skr-swap.log`
- Review [CLAUDE.md](CLAUDE.md) for architecture details
- Check [README.md](README.md) for API usage
- Verify transaction on Solana Explorer

## Security Reminders

1. **NEVER** commit `.env` or `config.yaml` with real keys
2. **NEVER** share your private keys
3. **ALWAYS** test with small amounts first
4. **USE** dedicated wallets for bot trading
5. **BACKUP** your keys securely
6. **MONITOR** the bot actively when running

---

Good luck with your SKR swapping! 🚀
