from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGridLayout,
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
from .settings import CurrencyRoute, TaxRule, WooStoreSettings
from .sync_engine import SyncEngine

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, engine: SyncEngine, scheduler: SyncScheduler) -> None:
        super().__init__()
        self.engine = engine
        self.scheduler = scheduler
        self.setWindowTitle("QuickBooksProject")
        self.resize(1120, 800)

        self.field_errors: dict[str, str] = {}
        self.settings_fields: dict[str, QLineEdit] = {}

        self._build_ui()
        self._apply_modern_style()
        self._load_settings_into_fields()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("QuickBooksProject Control Center")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Manage connections, sync jobs, tax rules, currency routing, and compatibility settings")
        subtitle.setObjectName("subtitleLabel")

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard_tab(), "Dashboard")
        self.tabs.addTab(self._build_settings_tab(), "Settings")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _build_dashboard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        settings_group = QGroupBox("Sync Runtime")
        settings_form = QFormLayout(settings_group)

        self.dry_run_checkbox = QCheckBox("Dry run (no writes to WooCommerce or QuickBooks)")
        self.dry_run_checkbox.setChecked(self.engine.dry_run)
        self.dry_run_checkbox.stateChanged.connect(self._on_dry_run_toggled)
        self.dry_run_checkbox.setToolTip("When enabled, sync operations simulate writes and log planned changes only.")

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(self.scheduler.interval_minutes)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        self.interval_spin.setToolTip("Scheduler run interval in minutes.")

        settings_form.addRow(self.dry_run_checkbox)
        settings_form.addRow("Scheduler interval (minutes)", self.interval_spin)

        button_row = QGridLayout()
        self.test_btn = self._create_action_button(
            "Test Connections",
            "Tests QuickBooks COM connectivity and all Woo store API credentials."
        )
        self.full_btn = self._create_action_button(
            "Run Inventory Full Sync",
            "Pushes complete QuickBooks inventory snapshot to Woo stores."
        )
        self.delta_btn = self._create_action_button(
            "Run Inventory Delta Sync",
            "Pushes only recently changed QuickBooks inventory to Woo stores."
        )
        self.sales_btn = self._create_action_button(
            "Import Woo Sales → QuickBooks",
            "Imports Woo completed/processing orders as QuickBooks sales receipts."
        )
        self.pause_btn = self._create_action_button(
            "Pause Scheduler",
            "Stops background interval jobs until resumed."
        )

        self.test_btn.clicked.connect(self._test_connections)
        self.full_btn.clicked.connect(self._run_full_sync)
        self.delta_btn.clicked.connect(self._run_delta_sync)
        self.sales_btn.clicked.connect(self._run_sales_import)
        self.pause_btn.clicked.connect(self._toggle_scheduler)

        button_row.addWidget(self.test_btn, 0, 0)
        button_row.addWidget(self.full_btn, 0, 1)
        button_row.addWidget(self.delta_btn, 1, 0)
        button_row.addWidget(self.sales_btn, 1, 1)
        button_row.addWidget(self.pause_btn, 2, 0, 1, 2)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setObjectName("statusLabel")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Operation log will appear here...")

        layout.addWidget(settings_group)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_text)
        return tab

    def _create_action_button(self, text: str, help_text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(help_text)
        return btn

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Required fields are explicit below. Hover the ? icons for guidance. "
            "Validation errors identify exactly which field to correct."
        )
        info.setWordWrap(True)

        group = QGroupBox("Configuration")
        form = QFormLayout(group)

        self.settings_fields = {
            "woo_store_name": QLineEdit(),
            "woo_base_url": QLineEdit(),
            "woo_consumer_key": QLineEdit(),
            "woo_consumer_secret": QLineEdit(),
            "default_tax_code": QLineEdit(),
            "default_tax_name": QLineEdit(),
            "tax_rules_json": QLineEdit(),
            "default_deposit_account": QLineEdit(),
            "currency_routes_json": QLineEdit(),
            "qbxml_versions": QLineEdit(),
        }

        self.settings_fields["woo_consumer_secret"].setEchoMode(QLineEdit.EchoMode.Password)

        self._add_form_row_help(form, "Woo store name", self.settings_fields["woo_store_name"], "Friendly name for this Woo store.")
        self._add_form_row_help(form, "Woo base URL", self.settings_fields["woo_base_url"], "Your WooCommerce site URL, e.g. https://store.example.com")
        self._add_form_row_help(form, "Woo consumer key", self.settings_fields["woo_consumer_key"], "REST API key from WooCommerce (typically starts with ck_).")
        self._add_form_row_help(form, "Woo consumer secret", self.settings_fields["woo_consumer_secret"], "REST API secret from WooCommerce (typically starts with cs_).")
        self._add_form_row_help(form, "Default tax code", self.settings_fields["default_tax_code"], "Fallback QuickBooks tax code when no rule matches.")
        self._add_form_row_help(form, "Default tax name", self.settings_fields["default_tax_name"], "Friendly fallback tax name shown in logs.")
        self._add_form_row_help(form, "Tax rules JSON", self.settings_fields["tax_rules_json"], "JSON list of rules: [{country,state,tax_code,tax_name,rate_percent}].")
        self._add_form_row_help(form, "Default deposit account", self.settings_fields["default_deposit_account"], "Fallback account if currency route is not found.")
        self._add_form_row_help(form, "Currency routes JSON", self.settings_fields["currency_routes_json"], "JSON list of routes: [{currency,deposit_account}].")
        self._add_form_row_help(form, "QBXML versions", self.settings_fields["qbxml_versions"], "Comma-separated compatibility fallback order, e.g. 13.0,12.0,11.0")

        self.settings_error_label = QLabel("")
        self.settings_error_label.setStyleSheet("color: #b91c1c;")
        self.settings_error_label.setWordWrap(True)

        button_row = QHBoxLayout()
        self.validate_btn = QPushButton("Validate Fields")
        self.save_btn = QPushButton("Save + Apply")
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

    def _add_form_row_help(self, form: QFormLayout, label: str, field: QWidget, help_text: str) -> None:
        label_widget = QWidget()
        hl = QHBoxLayout(label_widget)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        l = QLabel(label)
        q = QLabel("?")
        q.setObjectName("helpBadge")
        q.setToolTip(help_text)
        q.setStatusTip(help_text)

        hl.addWidget(l)
        hl.addWidget(q)
        hl.addStretch(1)

        form.addRow(label_widget, field)

    def _apply_modern_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #f4f7fb; color: #0f172a; font-size: 13px; }
            #titleLabel { font-size: 22px; font-weight: 700; color: #0b3b8c; }
            #subtitleLabel { color: #334155; }
            #statusLabel { background: #e2e8f0; border-radius: 8px; padding: 8px; }
            QGroupBox { border: 1px solid #dbe3ef; border-radius: 10px; margin-top: 10px; padding: 10px; font-weight: 600; background: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background: #1d4ed8; color: white; border: none; border-radius: 8px; padding: 8px 12px; }
            QPushButton:hover { background: #1e40af; }
            QPushButton:pressed { background: #1e3a8a; }
            QLineEdit, QSpinBox, QTextEdit { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; }
            #helpBadge { background: #e2e8f0; color: #1e293b; border: 1px solid #94a3b8; border-radius: 8px; padding: 1px 6px; font-weight: 700; }
            QTabWidget::pane { border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff; }
            QTabBar::tab { background: #e2e8f0; border-radius: 6px; padding: 8px 12px; margin-right: 4px; }
            QTabBar::tab:selected { background: #bfdbfe; color: #1e3a8a; }
            """
        )

    def _load_settings_into_fields(self) -> None:
        if not self.engine.woo_adapters:
            return
        store = self.engine.woo_adapters[0].settings
        self.settings_fields["woo_store_name"].setText(store.store_name)
        self.settings_fields["woo_base_url"].setText(str(store.base_url))
        self.settings_fields["woo_consumer_key"].setText(store.consumer_key)
        self.settings_fields["woo_consumer_secret"].setText(store.consumer_secret)

        self.settings_fields["default_tax_code"].setText(self.engine.settings.tax.default_tax_code)
        self.settings_fields["default_tax_name"].setText(self.engine.settings.tax.default_tax_name)
        self.settings_fields["tax_rules_json"].setText(
            json.dumps([r.model_dump() for r in self.engine.settings.tax.tax_rules])
        )

        self.settings_fields["default_deposit_account"].setText(
            self.engine.settings.currency_accounts.default_deposit_account
        )
        self.settings_fields["currency_routes_json"].setText(
            json.dumps([r.model_dump() for r in self.engine.settings.currency_accounts.routes])
        )
        self.settings_fields["qbxml_versions"].setText(", ".join(self.engine.qb_adapter.qbxml_versions))

    def _append_log(self, text: str) -> None:
        ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self.log_text.append(f"[{ts}] {text}")
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
        require("default_tax_code", "Default tax code")
        require("default_tax_name", "Default tax name")
        tax_rules_json = require("tax_rules_json", "Tax rules JSON")
        require("default_deposit_account", "Default deposit account")
        currency_routes_json = require("currency_routes_json", "Currency routes JSON")
        qbxml_versions = require("qbxml_versions", "QBXML versions")

        if base_url and not (base_url.startswith("https://") or base_url.startswith("http://")):
            self.field_errors["woo_base_url"] = "Woo base URL must start with http:// or https://"
        if consumer_key and not consumer_key.startswith("ck_"):
            self.field_errors["woo_consumer_key"] = "Woo consumer key should typically start with ck_"
        if consumer_secret and not consumer_secret.startswith("cs_"):
            self.field_errors["woo_consumer_secret"] = "Woo consumer secret should typically start with cs_"

        try:
            rules_data = json.loads(tax_rules_json)
            if not isinstance(rules_data, list):
                raise ValueError("Tax rules must be a JSON list")
            for row in rules_data:
                TaxRule.model_validate(row)
        except Exception as exc:  # noqa: BLE001
            self.field_errors["tax_rules_json"] = f"Tax rules JSON invalid: {exc}"

        try:
            routes_data = json.loads(currency_routes_json)
            if not isinstance(routes_data, list):
                raise ValueError("Currency routes must be a JSON list")
            for row in routes_data:
                CurrencyRoute.model_validate(row)
        except Exception as exc:  # noqa: BLE001
            self.field_errors["currency_routes_json"] = f"Currency routes JSON invalid: {exc}"

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

            for adapter in self.engine.woo_adapters:
                adapter.reconfigure(store)

            self.engine.settings.tax.default_tax_code = self.settings_fields["default_tax_code"].text().strip()
            self.engine.settings.tax.default_tax_name = self.settings_fields["default_tax_name"].text().strip()
            self.engine.settings.tax.tax_rules = [
                TaxRule.model_validate(row)
                for row in json.loads(self.settings_fields["tax_rules_json"].text().strip())
            ]

            self.engine.settings.currency_accounts.default_deposit_account = (
                self.settings_fields["default_deposit_account"].text().strip()
            )
            self.engine.settings.currency_accounts.routes = [
                CurrencyRoute.model_validate(row)
                for row in json.loads(self.settings_fields["currency_routes_json"].text().strip())
            ]

            versions = [v.strip() for v in self.settings_fields["qbxml_versions"].text().split(",") if v.strip()]
            self.engine.settings.quickbooks.qbxml_versions = versions
            self.engine.qb_adapter.qbxml_versions = versions

            self.settings_error_label.setStyleSheet("color: #166534;")
            self.settings_error_label.setText("Settings applied successfully for this runtime session.")
            self._append_log("Settings validated and applied at runtime.")
        except Exception as exc:  # noqa: BLE001
            self._error(
                "Failed to apply settings. Check highlighted fields and JSON syntax.",
                detail_exception=exc,
            )

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
            self._error("Connection test failed", detail_exception=exc)

    def _run_full_sync(self) -> None:
        try:
            summary = self.engine.run_full_sync()
            self._append_log(f"Inventory full sync complete: {summary.as_dict()}")
            self.status_label.setText(f"Inventory full sync status: {summary.status}")
        except Exception as exc:  # noqa: BLE001
            self._error("Inventory full sync failed", detail_exception=exc)

    def _run_delta_sync(self) -> None:
        try:
            summary = self.engine.run_delta_sync()
            self._append_log(f"Inventory delta sync complete: {summary.as_dict()}")
            self.status_label.setText(f"Inventory delta sync status: {summary.status}")
        except Exception as exc:  # noqa: BLE001
            self._error("Inventory delta sync failed", detail_exception=exc)

    def _run_sales_import(self) -> None:
        try:
            summary = self.engine.run_sales_import()
            self._append_log(f"Woo sales import complete: {summary.as_dict()}")
            self.status_label.setText(f"Sales import status: {summary.status}")
        except Exception as exc:  # noqa: BLE001
            self._error("Sales import failed", detail_exception=exc)

    def _toggle_scheduler(self) -> None:
        if self.pause_btn.text() == "Pause Scheduler":
            self.scheduler.stop()
            self.pause_btn.setText("Resume Scheduler")
            self._append_log("Scheduler paused")
            return
        self.scheduler.start()
        self.pause_btn.setText("Pause Scheduler")
        self._append_log("Scheduler resumed")

    def _error(self, message: str, detail_exception: Exception | None = None) -> None:
        detail_text = ""
        if detail_exception is not None:
            detail_text = "\n".join(traceback.format_exception(type(detail_exception), detail_exception, detail_exception.__traceback__))

        user_text = (
            f"{message}.\n\n"
            "Please check Settings values, API credentials, QBXML version fallback, and network connectivity."
        )
        self.status_label.setText(f"Error: {message}")
        self._append_log(f"Error: {message}")
        LOGGER.error("%s", message, exc_info=detail_exception)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Sync error")
        box.setText(user_text)
        if detail_text:
            box.setDetailedText(detail_text)
        box.exec()


def run_gui(engine: SyncEngine, scheduler: SyncScheduler) -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(engine=engine, scheduler=scheduler)
    window.show()
    scheduler.start()
    return app.exec()
