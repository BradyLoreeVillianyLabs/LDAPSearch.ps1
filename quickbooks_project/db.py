from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import ItemSyncOutcome, SyncRunSummary, WooOrder


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sync_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT NOT NULL,
  summary_json TEXT
);

CREATE TABLE IF NOT EXISTS sync_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  sku TEXT NOT NULL,
  qb_qty INTEGER NOT NULL,
  woo_qty_before INTEGER,
  woo_qty_after INTEGER,
  result TEXT NOT NULL,
  error TEXT,
  FOREIGN KEY(run_id) REFERENCES sync_runs(id)
);

CREATE TABLE IF NOT EXISTS sku_map(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  qb_item_ref TEXT NOT NULL,
  sku TEXT NOT NULL,
  woo_product_id INTEGER,
  woo_variation_id INTEGER,
  UNIQUE(qb_item_ref, sku)
);

CREATE TABLE IF NOT EXISTS processed_orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_name TEXT NOT NULL,
  woo_order_id TEXT NOT NULL,
  qb_txn_id TEXT,
  processed_at TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  UNIQUE(store_name, woo_order_id)
);

CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def start_run(self, status: str = "running") -> SyncRunSummary:
        started = datetime.now(timezone.utc)
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO sync_runs(started_at, status) VALUES (?, ?)",
                (started.isoformat(), status),
            )
            run_id = int(cur.lastrowid)
        return SyncRunSummary(run_id=run_id, started_at=started, ended_at=None, status=status)

    def log_item_outcome(self, run_id: int, outcome: ItemSyncOutcome) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_items(run_id, sku, qb_qty, woo_qty_before, woo_qty_after, result, error)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    outcome.sku,
                    outcome.qb_qty,
                    outcome.woo_qty_before,
                    outcome.woo_qty_after,
                    outcome.result.value,
                    outcome.error,
                ),
            )

    def order_already_processed(self, order: WooOrder) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_orders WHERE store_name=? AND woo_order_id=? LIMIT 1",
                (order.store_name, order.order_id),
            ).fetchone()
        return row is not None

    def mark_order_processed(
        self,
        order: WooOrder,
        status: str,
        qb_txn_id: str | None = None,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO processed_orders(store_name, woo_order_id, qb_txn_id, processed_at, status, error)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(store_name, woo_order_id)
                DO UPDATE SET qb_txn_id=excluded.qb_txn_id,
                              processed_at=excluded.processed_at,
                              status=excluded.status,
                              error=excluded.error
                """,
                (order.store_name, order.order_id, qb_txn_id, now, status, error),
            )

    def finish_run(self, summary: SyncRunSummary) -> None:
        summary.ended_at = datetime.now(timezone.utc)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sync_runs
                SET ended_at = ?, status = ?, summary_json = ?
                WHERE id = ?
                """,
                (
                    summary.ended_at.isoformat(),
                    summary.status,
                    json.dumps(summary.as_dict()),
                    summary.run_id,
                ),
            )
