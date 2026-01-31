# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: FastAPI app entry point and lifecycle (startup/shutdown).
- `services/`: core logic (signal routing, swap engine/manager, analytics, dashboard API).
- `exchange/`: external integrations (Jupiter, Solana RPC).
- `webhooks/`: webhook parsers and handlers.
- `models/`: Pydantic schemas.
- `utils/`: logging and wallet helpers.
- `data/`: SQLite database (`skr_swap.db`).
- `logs/`: runtime logs (`skr-swap.log`).
- `systemd/`: production service unit.
- `config.sample.yaml` and `.env`: configuration templates.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: create/activate venv.
- `pip install -r requirements.txt`: install dependencies.
- `cp config.sample.yaml config.yaml` and `cp .env.sample .env`: create configs.
- `uvicorn main:app --host 0.0.0.0 --port 4201 --reload`: run locally.
- `./test_webhook.sh`: send sample BUY/SELL webhooks for smoke testing.

## Coding Style & Naming Conventions
- Python, 4‑space indentation, PEP8-style naming (`snake_case`, `PascalCase`).
- Prefer explicit types in public methods; use Pydantic models for data shapes.
- Logging is via `loguru` (avoid `print`).
- Keep configuration in `config.yaml`; expand with env vars rather than hardcoding.

## Testing Guidelines
- No automated test suite is present today. Use `./test_webhook.sh` or `curl` for manual checks.
- If you introduce tests, place them under `tests/` with descriptive names (e.g., `test_swap_engine.py`).

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (e.g., “Add 24h price charts to dashboard”).
- PRs should explain behavior changes, configuration impacts, and any new env vars.
- Include a dashboard screenshot for UI changes.

## Security & Configuration Tips
- Never commit private keys. Use `.env` (`WALLET_PRIVATE_KEY`, `JUPITER_API_KEY`, `SOLANA_RPC_URL`).
- Price charts require a valid `JUPITER_API_KEY` for the price API.
- Use `data/` and `logs/` as the only write locations in production (see `systemd/skr-swap.service`).
