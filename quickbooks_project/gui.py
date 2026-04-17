from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .scheduler import SyncScheduler
from .settings import WooStoreSettings
from .sync_engine import SyncEngine

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, engine: SyncEngine, scheduler: SyncScheduler) -> None:
        super().__init__()
        self.engine = engine
        self.scheduler = scheduler
        self.setWindowTitle("QuickBooksProject")
        self.resize(1050, 760)

        self.field_errors: dict[str, str] = {}
        self.settings_fields: dict[str, QLineEdit] = {}

        self._build_ui()
        self._load_settings_into_fields()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard_tab(), "Dashboard")
        self.tabs.addTab(self._build_settings_tab(), "Settings")

        root.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _build_dashboard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        settings_group = QGroupBox("Sync Settings")
        settings_form = QFormLayout(settings_group)

        self.dry_run_checkbox = QCheckBox("Dry run (no writes to WooCommerce or QuickBooks)")
        self.dry_run_checkbox.setChecked(self.engine.dry_run)
        self.dry_run_checkbox.stateChanged.connect(self._on_dry_run_toggled)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(self.scheduler.interval_minutes)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)

        settings_form.addRow(self.dry_run_checkbox)
        settings_form.addRow("Scheduler interval (minutes)", self.interval_spin)

        button_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connections")
        self.full_btn = QPushButton("Run Inventory Full Sync")
        self.delta_btn = QPushButton("Run Inventory Delta Sync")
        self.sales_btn = QPushButton("Import Woo Sales → QuickBooks")
        self.pause_btn = QPushButton("Pause Scheduler")

        self.test_btn.clicked.connect(self._test_connections)
        self.full_btn.clicked.connect(self._run_full_sync)
        self.delta_btn.clicked.connect(self._run_delta_sync)
        self.sales_btn.clicked.connect(self._run_sales_import)
        self.pause_btn.clicked.connect(self._toggle_scheduler)

        button_row.addWidget(self.test_btn)
        button_row.addWidget(self.full_btn)
        button_row.addWidget(self.delta_btn)
        button_row.addWidget(self.sales_btn)
        button_row.addWidget(self.pause_btn)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        layout.addWidget(settings_group)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_text)
        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Enter required QuickBooks/WooCommerce settings below. "
            "Fields with validation errors are highlighted in red with explicit messages."
        )
        info.setWordWrap(True)

        group = QGroupBox("Required Configuration")
        form = QFormLayout(group)

        self.settings_fields = {
            "woo_store_name": QLineEdit(),
            "woo_base_url": QLineEdit(),
            "woo_consumer_key": QLineEdit(),
            "woo_consumer_secret": QLineEdit(),
            "tax_default_code": QLineEdit(),
            "tax_gst_code": QLineEdit(),
            "tax_hst_code": QLineEdit(),
            "tax_pst_code": QLineEdit(),
            "cad_deposit_account": QLineEdit(),
            "usd_deposit_account": QLineEdit(),
            "qbxml_versions": QLineEdit(),
        }

        self.settings_fields["woo_consumer_secret"].setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Woo store name", self.settings_fields["woo_store_name"])
        form.addRow("Woo base URL (https://...)", self.settings_fields["woo_base_url"])
        form.addRow("Woo consumer key", self.settings_fields["woo_consumer_key"])
        form.addRow("Woo consumer secret", self.settings_fields["woo_consumer_secret"])
        form.addRow("Default tax code", self.settings_fields["tax_default_code"])
        form.addRow("GST tax code", self.settings_fields["tax_gst_code"])
        form.addRow("HST tax code", self.settings_fields["tax_hst_code"])
        form.addRow("PST tax code", self.settings_fields["tax_pst_code"])
        form.addRow("CAD deposit account", self.settings_fields["cad_deposit_account"])
        form.addRow("USD deposit account", self.settings_fields["usd_deposit_account"])
        form.addRow("QBXML versions (comma-separated)", self.settings_fields["qbxml_versions"])

        self.settings_error_label = QLabel("")
        self.settings_error_label.setStyleSheet("color: #b91c1c;")
        self.settings_error_label.setWordWrap(True)

        button_row = QHBoxLayout()
        self.validate_btn = QPushButton("Validate Fields")
        self.save_btn = QPushButton("Save + Apply Runtime Settings")
        self.validate_btn.clicked.connect(self._validate_settings_form)
        self.save_btn.clicked.connect(self._save_and_apply_settings)

        button_row.addWidget(self.validate_btn)
        button_row.addWidget(self.save_btn)

        layout.addWidget(info)
        layout.addWidget(group)
        layout.addWidget(self.settings_error_label)
        layout.addLayout(button_row)
        layout.addStretch(1)
        return tab

    def _load_settings_into_fields(self) -> None:
        if not self.engine.woo_adapters:
            return
        store = self.engine.woo_adapters[0].settings
        self.settings_fields["woo_store_name"].setText(store.store_name)
        self.settings_fields["woo_base_url"].setText(str(store.base_url))
        self.settings_fields["woo_consumer_key"].setText(store.consumer_key)
        self.settings_fields["woo_consumer_secret"].setText(store.consumer_secret)

        self.settings_fields["tax_default_code"].setText(self.engine.settings.tax.default_tax_code)
        self.settings_fields["tax_gst_code"].setText(self.engine.settings.tax.gst_tax_code)
        self.settings_fields["tax_hst_code"].setText(self.engine.settings.tax.hst_tax_code)
        self.settings_fields["tax_pst_code"].setText(self.engine.settings.tax.pst_tax_code)

        self.settings_fields["cad_deposit_account"].setText(self.engine.settings.currency_accounts.cad_deposit_account)
        self.settings_fields["usd_deposit_account"].setText(self.engine.settings.currency_accounts.usd_deposit_account)
        self.settings_fields["qbxml_versions"].setText(", ".join(self.engine.qb_adapter.qbxml_versions))

    def _append_log(self, text: str) -> None:
        self.log_text.append(text)
        LOGGER.info(text)

    def _on_dry_run_toggled(self, state: int) -> None:
        self.engine.dry_run = state == Qt.CheckState.Checked.value
        self._append_log(f"Dry-run mode set to {self.engine.dry_run}")

    def _on_interval_changed(self, value: int) -> None:
        self.scheduler.interval_minutes = value
        self._append_log(f"Interval changed to {value} minutes (restart scheduler to apply)")

    def _validate_settings_form(self) -> bool:
        self.field_errors.clear()
        self._clear_field_error_styles()

        def require(name: str, label: str) -> str:
            value = self.settings_fields[name].text().strip()
            if not value:
                self.field_errors[name] = f"{label} is required."
            return value

        store_name = require("woo_store_name", "Woo store name")
        base_url = require("woo_base_url", "Woo base URL")
        consumer_key = require("woo_consumer_key", "Woo consumer key")
        consumer_secret = require("woo_consumer_secret", "Woo consumer secret")

        require("tax_default_code", "Default tax code")
        require("tax_gst_code", "GST tax code")
        require("tax_hst_code", "HST tax code")
        require("tax_pst_code", "PST tax code")
        require("cad_deposit_account", "CAD deposit account")
        require("usd_deposit_account", "USD deposit account")

        qbxml_versions = require("qbxml_versions", "QBXML versions")

        if base_url and not (base_url.startswith("https://") or base_url.startswith("http://")):
            self.field_errors["woo_base_url"] = "Woo base URL must start with http:// or https://"
        if consumer_key and not consumer_key.startswith("ck_"):
            self.field_errors["woo_consumer_key"] = "Woo consumer key should typically start with ck_"
        if consumer_secret and not consumer_secret.startswith("cs_"):
            self.field_errors["woo_consumer_secret"] = "Woo consumer secret should typically start with cs_"

        versions = [v.strip() for v in qbxml_versions.split(",") if v.strip()]
        if not versions:
            self.field_errors["qbxml_versions"] = "Provide at least one QBXML version (e.g. 13.0,12.0,11.0)."

        if self.field_errors:
            self._show_field_errors()
            return False

        self.settings_error_label.setText(
            f"Validation passed for store '{store_name}'. You can now save/apply settings."
        )
        return True

    def _save_and_apply_settings(self) -> None:
        if not self._validate_settings_form():
            return

        try:
            store = WooStoreSettings(
                store_name=self.settings_fields["woo_store_name"].text().strip(),
                base_url=self.settings_fields["woo_base_url"].text().strip(),
                consumer_key=self.settings_fields["woo_consumer_key"].text().strip(),
                consumer_secret=self.settings_fields["woo_consumer_secret"].text().strip(),
                enabled=True,
            )

            # Apply Woo settings to all adapters at runtime for consistency.
            for adapter in self.engine.woo_adapters:
                adapter.reconfigure(store)

            self.engine.settings.tax.default_tax_code = self.settings_fields["tax_default_code"].text().strip()
            self.engine.settings.tax.gst_tax_code = self.settings_fields["tax_gst_code"].text().strip()
            self.engine.settings.tax.hst_tax_code = self.settings_fields["tax_hst_code"].text().strip()
            self.engine.settings.tax.pst_tax_code = self.settings_fields["tax_pst_code"].text().strip()

            self.engine.settings.currency_accounts.cad_deposit_account = (
                self.settings_fields["cad_deposit_account"].text().strip()
            )
            self.engine.settings.currency_accounts.usd_deposit_account = (
                self.settings_fields["usd_deposit_account"].text().strip()
            )

            versions = [v.strip() for v in self.settings_fields["qbxml_versions"].text().split(",") if v.strip()]
            self.engine.settings.quickbooks.qbxml_versions = versions
            self.engine.qb_adapter.qbxml_versions = versions

            self.settings_error_label.setStyleSheet("color: #166534;")
            self.settings_error_label.setText("Settings applied successfully for this runtime session.")
            self._append_log("Settings validated and applied at runtime.")
        except Exception as exc:  # noqa: BLE001
            self.settings_error_label.setStyleSheet("color: #b91c1c;")
            self.settings_error_label.setText(f"Could not apply settings: {exc}")

    def _clear_field_error_styles(self) -> None:
        for field in self.settings_fields.values():
            field.setStyleSheet("")
            palette = field.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
            field.setPalette(palette)
        self.settings_error_label.setStyleSheet("color: #b91c1c;")
        self.settings_error_label.setText("")

    def _show_field_errors(self) -> None:
        lines = []
        for key, message in self.field_errors.items():
            field = self.settings_fields[key]
            field.setStyleSheet("border: 1px solid #dc2626;")
            palette = field.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor("#fef2f2"))
            field.setPalette(palette)
            lines.append(f"• {message}")
        self.settings_error_label.setText("Please fix the following fields:\n" + "\n".join(lines))

    def _test_connections(self) -> None:
        try:
            qb_ok = self.engine.qb_adapter.test_connection()
            store_results = []
            for adapter in self.engine.woo_adapters:
                status = "OK" if adapter.test_connection() else "FAILED"
                store_results.append(f"{adapter.store_name}: {status}")
            msg = f"QuickBooks: {'OK' if qb_ok else 'FAILED'} | Woo: {'; '.join(store_results)}"
            self.status_label.setText(msg)
            self._append_log(msg)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _run_full_sync(self) -> None:
        try:
            summary = self.engine.run_full_sync()
            self._append_log(f"Inventory full sync complete: {summary.as_dict()}")
            self.status_label.setText(f"Inventory full sync status: {summary.status}")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _run_delta_sync(self) -> None:
        try:
            summary = self.engine.run_delta_sync()
            self._append_log(f"Inventory delta sync complete: {summary.as_dict()}")
            self.status_label.setText(f"Inventory delta sync status: {summary.status}")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _run_sales_import(self) -> None:
        try:
            summary = self.engine.run_sales_import()
            self._append_log(f"Woo sales import complete: {summary.as_dict()}")
            self.status_label.setText(f"Sales import status: {summary.status}")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _toggle_scheduler(self) -> None:
        if self.pause_btn.text() == "Pause Scheduler":
            self.scheduler.stop()
            self.pause_btn.setText("Resume Scheduler")
            self._append_log("Scheduler paused")
            return
        self.scheduler.start()
        self.pause_btn.setText("Pause Scheduler")
        self._append_log("Scheduler resumed")

    def _error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")
        self._append_log(f"Error: {message}")
        QMessageBox.critical(self, "Sync error", message)


def run_gui(engine: SyncEngine, scheduler: SyncScheduler) -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(engine=engine, scheduler=scheduler)
    window.show()
    scheduler.start()
    return app.exec()
