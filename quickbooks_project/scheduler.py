from __future__ import annotations

import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .sync_engine import SyncEngine

LOGGER = logging.getLogger(__name__)


class SyncScheduler:
    def __init__(self, engine: SyncEngine, interval_minutes: int) -> None:
        self.engine = engine
        self.interval_minutes = interval_minutes
        self._lock = threading.Lock()
        self._scheduler = self._new_scheduler()

    @staticmethod
    def _new_scheduler() -> BackgroundScheduler:
        return BackgroundScheduler(job_defaults={"max_instances": 1, "coalesce": True})

    def start(self) -> None:
        if self._scheduler.running:
            LOGGER.info("Scheduler already running")
            return

        self._scheduler.add_job(
            self._run_inventory_delta_safely,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="inventory_delta_sync",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._run_sales_import_safely,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="woo_sales_import",
            replace_existing=True,
        )
        self._scheduler.start()
        LOGGER.info("Scheduler started at %s-minute interval", self.interval_minutes)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            LOGGER.info("Scheduler stopped")
            # APScheduler instances are not always safe to restart after shutdown,
            # so create a fresh scheduler instance for resume.
            self._scheduler = self._new_scheduler()

    def _run_inventory_delta_safely(self) -> None:
        self._run_with_lock(self.engine.run_delta_sync)

    def _run_sales_import_safely(self) -> None:
        self._run_with_lock(self.engine.run_sales_import)

    def _run_with_lock(self, fn) -> None:  # type: ignore[no-untyped-def]
        if not self._lock.acquire(blocking=False):
            LOGGER.warning("Skipped scheduled run due to active sync")
            return
        try:
            fn()
        finally:
            self._lock.release()
