from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .db import Database
from .models import InventoryItem, ItemSyncOutcome, SyncItemResult, SyncRunSummary, TaxDecision, WooOrder
from .qb_adapter import QuickBooksAdapter
from .settings import AppSettings, CurrencyRoute, TaxRule
from .woo_adapter import WooAdapter
from .spreadsheet_router import SpreadsheetRouter

LOGGER = logging.getLogger(__name__)


class SyncEngine:
    def __init__(
        self,
        db: Database,
        qb_adapter: QuickBooksAdapter,
        woo_adapters: list[WooAdapter],
        settings: AppSettings,
        spreadsheet_router: SpreadsheetRouter | None = None,
    ) -> None:
        self.db = db
        self.qb_adapter = qb_adapter
        self.woo_adapters = woo_adapters
        self.settings = settings
        self.spreadsheet_router = spreadsheet_router
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
                    if self.spreadsheet_router is not None:
                        self.spreadsheet_router.export_order(order)
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
        country = order.country.upper().strip()
        state = order.state.upper().strip()

        for rule in self.settings.tax.tax_rules:
            r = TaxRule.model_validate(rule)
            if r.country.upper() != country:
                continue
            if r.state != "*" and r.state.upper() != state:
                continue
            return TaxDecision(tax_code=r.tax_code, tax_name=r.tax_name, rate_percent=r.rate_percent)

        return TaxDecision(
            tax_code=self.settings.tax.default_tax_code,
            tax_name=self.settings.tax.default_tax_name,
            rate_percent=self.settings.tax.default_tax_rate_percent,
        )

    def _decide_deposit_account(self, currency: str) -> str:
        c = currency.upper().strip()
        for route in self.settings.currency_accounts.routes:
            r = CurrencyRoute.model_validate(route)
            if r.currency.upper() == c:
                return r.deposit_account
        return self.settings.currency_accounts.default_deposit_account
