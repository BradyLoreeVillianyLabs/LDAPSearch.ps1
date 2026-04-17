from __future__ import annotations

import argparse

from .db import Database
from .gui import run_gui
from .host_setup import HostSetupManager
from .logging_config import setup_logging
from .qb_adapter import QuickBooksAdapter
from .scheduler import SyncScheduler
from .settings import load_settings
from .sync_engine import SyncEngine
from .spreadsheet_router import SpreadsheetRouter
from .woo_adapter import WooAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="QuickBooksProject desktop sync app")
    parser.add_argument("--first-run", action="store_true", help="Open app on Settings tab for initial setup")
    args = parser.parse_args()

    settings = load_settings()
    setup_logging(settings.log_path)

    host_setup = HostSetupManager(settings)
    host_result = host_setup.prepare()

    db = Database(settings.database_path)
    db.init_schema()

    active_stores = settings.active_stores()
    if not active_stores:
        raise RuntimeError("No WooCommerce stores configured. Set QB_WOO__WOO or QB_WOO__WOO_STORES.")

    qb_adapter = QuickBooksAdapter(app_name=settings.app_name, qbxml_versions=settings.quickbooks.qbxml_versions)
    woo_adapters = [WooAdapter(store) for store in active_stores]
    spreadsheet_router = SpreadsheetRouter(settings.spreadsheet)
    engine = SyncEngine(
        db=db,
        qb_adapter=qb_adapter,
        woo_adapters=woo_adapters,
        settings=settings,
        spreadsheet_router=spreadsheet_router,
    )
    scheduler = SyncScheduler(engine=engine, interval_minutes=settings.sync.interval_minutes)

    start_tab = "settings" if args.first_run else "dashboard"
    return run_gui(
        engine=engine,
        scheduler=scheduler,
        host_setup_manager=host_setup,
        host_setup_result=host_result,
        start_tab=start_tab,
    )


if __name__ == "__main__":
    raise SystemExit(main())
