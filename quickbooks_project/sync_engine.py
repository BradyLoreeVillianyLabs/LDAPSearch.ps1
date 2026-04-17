from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .db import Database
from .models import InventoryItem, ItemSyncOutcome, SyncItemResult, SyncRunSummary, TaxDecision, WooOrder
from .qb_adapter import QuickBooksAdapter
from .settings import AppSettings
from .woo_adapter import WooAdapter

LOGGER = logging.getLogger(__name__)


class SyncEngine:
    def __init__(
        self,
        db: Database,
        qb_adapter: QuickBooksAdapter,
        woo_adapters: list[WooAdapter],
        settings: AppSettings,
    ) -> None:
        self.db = db
        self.qb_adapter = qb_adapter
        self.woo_adapters = woo_adapters
        self.settings = settings
        self.dry_run = settings.sync.dry_run
        self.delta_minutes_lookback = settings.sync.delta_minutes_lookback
        self.order_lookback_minutes = settings.sync.order_lookback_minutes

    def run_full_sync(self) -> SyncRunSummary:
        """Push QB inventory to every active Woo store."""
        return self._run_inventory_sync(modified_since=None)

    def run_delta_sync(self) -> SyncRunSummary:
        since = datetime.now(timezone.utc) - timedelta(minutes=self.delta_minutes_lookback)
        return self._run_inventory_sync(modified_since=since)

    def run_sales_import(self) -> SyncRunSummary:
        """Pull Woo orders and post them to QuickBooks Sales Receipts."""
        run = self.db.start_run(status="running")
        try:
            orders: list[WooOrder] = []
            for adapter in self.woo_adapters:
                orders.extend(adapter.fetch_recent_orders(minutes_lookback=self.order_lookback_minutes))

            run.orders_total = len(orders)
            for order in orders:
                if self.db.order_already_processed(order):
                    run.orders_skipped += 1
                    continue

                try:
                    tax = self._decide_tax(order)
                    deposit_account = self._decide_deposit_account(order.currency)
                    txn_id = self.qb_adapter.record_sales_receipt(
                        order=order,
                        tax=tax,
                        deposit_to_account=deposit_account,
                        dry_run=self.dry_run,
                    )
                    self.db.mark_order_processed(order, status="posted", qb_txn_id=txn_id)
                    run.orders_posted += 1
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Failed posting Woo order %s (%s)", order.order_id, order.store_name)
                    self.db.mark_order_processed(order, status="failed", error=str(exc))
                    run.orders_failed += 1

            run.status = "success" if run.orders_failed == 0 else "partial_failure"
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.orders_failed += 1
            LOGGER.exception("Sales import failed: %s", exc)
        finally:
            self.db.finish_run(run)
        return run

    def _run_inventory_sync(self, modified_since: datetime | None) -> SyncRunSummary:
        run = self.db.start_run(status="running")
        try:
            items = self.qb_adapter.fetch_inventory_items(modified_since=modified_since)
            run.items_total = len(items)
            for item in items:
                for adapter in self.woo_adapters:
                    outcome = self._sync_one_store(item, adapter)
                    self.db.log_item_outcome(run.run_id, outcome)
                    if outcome.result is SyncItemResult.SUCCESS:
                        run.items_updated += 1
                    elif outcome.result is SyncItemResult.NOOP:
                        run.items_noop += 1
                    elif outcome.result is SyncItemResult.SKIPPED:
                        run.items_skipped += 1
                    elif outcome.result is SyncItemResult.FAILED:
                        run.items_failed += 1
            run.status = "success" if run.items_failed == 0 else "partial_failure"
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.items_failed += 1
            LOGGER.exception("Inventory sync failed: %s", exc)
        finally:
            self.db.finish_run(run)
        return run

    def _sync_one_store(self, item: InventoryItem, adapter: WooAdapter) -> ItemSyncOutcome:
        try:
            woo_ref = adapter.find_by_sku(item.sku)
            if not woo_ref:
                return ItemSyncOutcome(
                    sku=f"{adapter.store_name}:{item.sku}",
                    qb_qty=item.qty_on_hand,
                    woo_qty_before=None,
                    woo_qty_after=None,
                    result=SyncItemResult.SKIPPED,
                    error="No WooCommerce product found for SKU",
                )

            before = woo_ref.stock_quantity
            if before == item.qty_on_hand:
                return ItemSyncOutcome(
                    sku=f"{adapter.store_name}:{item.sku}",
                    qb_qty=item.qty_on_hand,
                    woo_qty_before=before,
                    woo_qty_after=before,
                    result=SyncItemResult.NOOP,
                )

            if self.dry_run:
                return ItemSyncOutcome(
                    sku=f"{adapter.store_name}:{item.sku}",
                    qb_qty=item.qty_on_hand,
                    woo_qty_before=before,
                    woo_qty_after=item.qty_on_hand,
                    result=SyncItemResult.SUCCESS,
                )

            adapter.update_stock(woo_ref, item.qty_on_hand)
            return ItemSyncOutcome(
                sku=f"{adapter.store_name}:{item.sku}",
                qb_qty=item.qty_on_hand,
                woo_qty_before=before,
                woo_qty_after=item.qty_on_hand,
                result=SyncItemResult.SUCCESS,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed syncing SKU=%s for store=%s", item.sku, adapter.store_name)
            return ItemSyncOutcome(
                sku=f"{adapter.store_name}:{item.sku}",
                qb_qty=item.qty_on_hand,
                woo_qty_before=None,
                woo_qty_after=None,
                result=SyncItemResult.FAILED,
                error=str(exc),
            )

    def _decide_tax(self, order: WooOrder) -> TaxDecision:
        # Canada defaults by province (simplified; can be replaced by tax table file later)
        province = order.state.upper()
        country = order.country.upper()
        if country != "CA":
            return TaxDecision(tax_code=self.settings.tax.default_tax_code, tax_name="No Tax", rate_percent=0.0)

        hst_provinces = {"ON", "NB", "NL", "NS", "PE"}
        pst_provinces = {"BC", "SK", "MB"}

        if province in hst_provinces:
            return TaxDecision(tax_code=self.settings.tax.hst_tax_code, tax_name="HST", rate_percent=13.0)
        if province in pst_provinces:
            return TaxDecision(tax_code=self.settings.tax.pst_tax_code, tax_name="PST+GST", rate_percent=12.0)
        return TaxDecision(tax_code=self.settings.tax.gst_tax_code, tax_name="GST", rate_percent=5.0)

    def _decide_deposit_account(self, currency: str) -> str:
        c = currency.upper().strip()
        if c == "USD":
            return self.settings.currency_accounts.usd_deposit_account
        return self.settings.currency_accounts.cad_deposit_account
