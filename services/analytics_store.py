"""SQLite persistence for signals, swaps, and analytics."""
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


class AnalyticsStore:
    """SQLite-backed store for swap bot analytics."""

    def __init__(self, db_path: str = "./data/skr_swap.db"):
        self.db_path = db_path
        dir_name = os.path.dirname(os.path.abspath(self.db_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            # Signals table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    amount REAL,
                    price REAL,
                    note TEXT,
                    raw_payload TEXT,
                    account_id TEXT
                )
            """)

            # Swaps table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS swaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    account_label TEXT,
                    input_token TEXT NOT NULL,
                    output_token TEXT NOT NULL,
                    input_amount REAL NOT NULL,
                    output_amount REAL,
                    price REAL,
                    slippage REAL,
                    fee_lamports INTEGER,
                    fee_usd REAL,
                    signature TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    meta TEXT,
                    input_token_usd_price REAL,
                    output_token_usd_price REAL,
                    input_usd REAL,
                    output_usd REAL
                )
            """)

            # Add USD price columns if they don't exist (migration)
            try:
                conn.execute("ALTER TABLE swaps ADD COLUMN input_token_usd_price REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                conn.execute("ALTER TABLE swaps ADD COLUMN output_token_usd_price REAL")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE swaps ADD COLUMN input_usd REAL")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE swaps ADD COLUMN output_usd REAL")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE swaps ADD COLUMN fee_lamports INTEGER")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE swaps ADD COLUMN fee_usd REAL")
            except sqlite3.OperationalError:
                pass

            # Wallet state table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallet_state (
                    account_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    balance REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, token)
                )
            """)

            # Price ticks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Create indexes
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_received_at ON signals(received_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_swaps_created_at ON swaps(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_ts ON price_ticks(symbol, timestamp DESC)"
            )

    def record_signal(
        self,
        action: str,
        symbol: str,
        account_id: Optional[str] = None,
        amount: Optional[float] = None,
        price: Optional[float] = None,
        note: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Record a received signal."""
        received_at = datetime.now(timezone.utc).isoformat()
        raw_payload = json.dumps(payload or {}, default=str)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO signals (received_at, action, symbol, amount, price, note, raw_payload, account_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (received_at, action, symbol, amount, price, note, raw_payload, account_id),
            )
            return cur.lastrowid

    def create_swap(
        self,
        account_id: str,
        account_label: Optional[str],
        input_token: str,
        output_token: str,
        input_amount: float,
        meta: Optional[Dict[str, Any]] = None,
        input_token_usd_price: Optional[float] = None,
        input_usd: Optional[float] = None,
    ) -> int:
        """Create a new swap record with USD prices at trade time."""
        created_at = datetime.now(timezone.utc).isoformat()
        meta_dump = json.dumps(meta or {}, default=str)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO swaps (account_id, account_label, input_token, output_token,
                                   input_amount, status, created_at, meta,
                                   input_token_usd_price, input_usd)
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
                """,
                (account_id, account_label, input_token, output_token, input_amount,
                 created_at, meta_dump, input_token_usd_price, input_usd),
            )
            return cur.lastrowid

    def complete_swap(
        self,
        swap_id: int,
        signature: str,
        output_amount: float,
        price: Optional[float] = None,
        slippage: Optional[float] = None,
        output_token_usd_price: Optional[float] = None,
        output_usd: Optional[float] = None,
        fee_lamports: Optional[int] = None,
        fee_usd: Optional[float] = None,
    ) -> None:
        """Mark a swap as completed with USD prices at trade time."""
        completed_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE swaps
                SET status = 'COMPLETED',
                    signature = ?,
                    output_amount = ?,
                    price = ?,
                    slippage = ?,
                    completed_at = ?,
                    output_token_usd_price = ?,
                    output_usd = ?,
                    fee_lamports = ?,
                    fee_usd = ?
                WHERE id = ?
                """,
                (signature, output_amount, price, slippage, completed_at,
                 output_token_usd_price, output_usd, fee_lamports, fee_usd, swap_id),
            )

    def fail_swap(self, swap_id: int, error: str) -> None:
        """Mark a swap as failed."""
        completed_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE swaps
                SET status = 'FAILED',
                    error = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (error, completed_at, swap_id),
            )

    def list_swaps(
        self,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List swaps with optional filters."""
        query = "SELECT * FROM swaps WHERE 1=1"
        params: List[Any] = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def get_output_change_totals(
        self,
        since_iso: str,
        account_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Get percent change per output token since a timestamp.

        Returns dict of {token: {first, last, change_pct}}.
        """
        query = """
            SELECT output_token, output_amount, created_at
            FROM swaps
            WHERE status = 'COMPLETED'
              AND created_at >= ?
        """
        params: List[Any] = [since_iso]

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        query += " ORDER BY created_at ASC"

        first: Dict[str, float] = {}
        last: Dict[str, float] = {}

        with self._connect() as conn:
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                token = row["output_token"]
                amount = row["output_amount"]
                if amount is None:
                    continue
                amount_val = float(amount)
                if token not in first:
                    first[token] = amount_val
                last[token] = amount_val

        totals: Dict[str, Dict[str, float]] = {}
        for token, first_val in first.items():
            last_val = last.get(token)
            if last_val is None or first_val == 0:
                continue
            change_pct = ((last_val - first_val) / first_val) * 100
            totals[token] = {
                "first": first_val,
                "last": last_val,
                "change_pct": change_pct,
            }

        return totals

    def get_previous_completed_swap(
        self,
        account_id: str,
        output_token: str,
        before_created_at: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent completed swap before a timestamp for an output token."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT *
                FROM swaps
                WHERE account_id = ?
                  AND status = 'COMPLETED'
                  AND output_token = ?
                  AND created_at < ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (account_id, output_token, before_created_at),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_last_completed_swap(
        self,
        account_id: str,
        input_token: Optional[str] = None,
        output_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent completed swap for an account (optional token filters)."""
        query = "SELECT * FROM swaps WHERE account_id = ? AND status = 'COMPLETED'"
        params: List[Any] = [account_id]

        if input_token:
            query += " AND input_token = ?"
            params.append(input_token)

        if output_token:
            query += " AND output_token = ?"
            params.append(output_token)

        query += " ORDER BY completed_at DESC LIMIT 1"

        with self._connect() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def list_signals(
        self,
        account_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List recent signals."""
        query = "SELECT * FROM signals WHERE 1=1"
        params: List[Any] = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        query += " ORDER BY received_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def update_wallet_balance(
        self,
        account_id: str,
        token: str,
        balance: float,
    ) -> None:
        """Update wallet token balance."""
        updated_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO wallet_state (account_id, token, balance, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account_id, token)
                DO UPDATE SET balance = excluded.balance, updated_at = excluded.updated_at
                """,
                (account_id, token, balance, updated_at),
            )

    def get_wallet_balances(self, account_id: str) -> Dict[str, float]:
        """Get all token balances for an account."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT token, balance FROM wallet_state WHERE account_id = ?",
                (account_id,),
            )
            return {row["token"]: row["balance"] for row in cur.fetchall()}

    def record_price(self, symbol: str, price: float) -> None:
        """Record a price tick."""
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO price_ticks (symbol, price, timestamp) VALUES (?, ?, ?)",
                (symbol, price, timestamp),
            )

    def list_price_ticks(
        self,
        symbol: str,
        hours: int = 24,
        limit: int = 1440,
    ) -> List[Dict[str, Any]]:
        """List price ticks for a symbol in the last N hours."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT price, timestamp
                FROM price_ticks
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (symbol, cutoff, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def cleanup_old_prices(self, days: int = 7) -> int:
        """Delete price ticks older than N days."""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM price_ticks WHERE timestamp < ?",
                (cutoff,),
            )
            return cur.rowcount
