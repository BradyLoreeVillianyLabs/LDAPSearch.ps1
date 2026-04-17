from __future__ import annotations

from .db import Database
from .gui import run_gui
from .logging_config import setup_logging
from .qb_adapter import QuickBooksAdapter
from .scheduler import SyncScheduler
from .settings import load_settings
from .sync_engine import SyncEngine
from .woo_adapter import WooAdapter


def main() -> int:
    settings = load_settings()
    setup_logging(settings.log_path)

    db = Database(settings.database_path)
    db.init_schema()

    active_stores = settings.active_stores()
    if not active_stores:
        raise RuntimeError("No WooCommerce stores configured. Set QB_WOO__WOO or QB_WOO__WOO_STORES.")

    qb_adapter = QuickBooksAdapter(app_name=settings.app_name, qbxml_versions=settings.quickbooks.qbxml_versions)
    woo_adapters = [WooAdapter(store) for store in active_stores]
    engine = SyncEngine(
        db=db,
        qb_adapter=qb_adapter,
        woo_adapters=woo_adapters,
        settings=settings,
    )
    scheduler = SyncScheduler(engine=engine, interval_minutes=settings.sync.interval_minutes)

    return run_gui(engine=engine, scheduler=scheduler)


if __name__ == "__main__":
    raise SystemExit(main())
