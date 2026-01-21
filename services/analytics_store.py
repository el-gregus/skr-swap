"""SQLite persistence for signals, swaps, and analytics."""
import json
import os
import sqlite3
from datetime import datetime, timezone
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
                    signature TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    meta TEXT
                )
            """)

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
        received_at = datetime.utcnow().isoformat()
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
    ) -> int:
        """Create a new swap record."""
        created_at = datetime.utcnow().isoformat()
        meta_dump = json.dumps(meta or {}, default=str)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO swaps (account_id, account_label, input_token, output_token,
                                   input_amount, status, created_at, meta)
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (account_id, account_label, input_token, output_token, input_amount, created_at, meta_dump),
            )
            return cur.lastrowid

    def complete_swap(
        self,
        swap_id: int,
        signature: str,
        output_amount: float,
        price: Optional[float] = None,
        slippage: Optional[float] = None,
    ) -> None:
        """Mark a swap as completed."""
        completed_at = datetime.utcnow().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE swaps
                SET status = 'COMPLETED',
                    signature = ?,
                    output_amount = ?,
                    price = ?,
                    slippage = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (signature, output_amount, price, slippage, completed_at, swap_id),
            )

    def fail_swap(self, swap_id: int, error: str) -> None:
        """Mark a swap as failed."""
        completed_at = datetime.utcnow().isoformat()

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
        updated_at = datetime.utcnow().isoformat()

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
        timestamp = datetime.utcnow().isoformat()

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO price_ticks (symbol, price, timestamp) VALUES (?, ?, ?)",
                (symbol, price, timestamp),
            )

    def cleanup_old_prices(self, days: int = 7) -> int:
        """Delete price ticks older than N days."""
        from datetime import timedelta

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM price_ticks WHERE timestamp < ?",
                (cutoff,),
            )
            return cur.rowcount
