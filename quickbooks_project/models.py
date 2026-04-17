from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SyncItemResult(str, Enum):
    SUCCESS = "success"
    NOOP = "noop"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(slots=True)
class InventoryItem:
    sku: str
    qty_on_hand: int
    item_ref: str
    last_modified: datetime | None = None


@dataclass(slots=True)
class WooProductRef:
    sku: str
    product_id: int | None = None
    variation_id: int | None = None
    stock_quantity: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: float
    line_total: float


@dataclass(slots=True)
class WooOrder:
    store_name: str
    order_id: str
    created_at: datetime
    currency: str
    country: str
    state: str
    city: str
    email: str
    lines: list[OrderLine] = field(default_factory=list)
    total_tax: float = 0.0
    total_amount: float = 0.0


@dataclass(slots=True)
class TaxDecision:
    tax_code: str
    tax_name: str
    rate_percent: float


@dataclass(slots=True)
class ItemSyncOutcome:
    sku: str
    qb_qty: int
    woo_qty_before: int | None
    woo_qty_after: int | None
    result: SyncItemResult
    error: str | None = None


@dataclass(slots=True)
class SyncRunSummary:
    run_id: int
    started_at: datetime
    ended_at: datetime | None
    status: str
    items_total: int = 0
    items_updated: int = 0
    items_noop: int = 0
    items_skipped: int = 0
    items_failed: int = 0
    orders_total: int = 0
    orders_posted: int = 0
    orders_skipped: int = 0
    orders_failed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "items_total": self.items_total,
            "items_updated": self.items_updated,
            "items_noop": self.items_noop,
            "items_skipped": self.items_skipped,
            "items_failed": self.items_failed,
            "orders_total": self.orders_total,
            "orders_posted": self.orders_posted,
            "orders_skipped": self.orders_skipped,
            "orders_failed": self.orders_failed,
        }
