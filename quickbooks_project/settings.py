from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class QuickBooksSettings(BaseModel):
    # Ordered by preferred version, fallback sequence for compatibility.
    qbxml_versions: list[str] = Field(default_factory=lambda: ["13.0", "12.0", "11.0", "10.0", "8.0"])


class WooStoreSettings(BaseModel):
    store_name: str = Field(min_length=1)
    base_url: HttpUrl
    consumer_key: str = Field(min_length=3)
    consumer_secret: str = Field(min_length=3)
    timeout_seconds: int = Field(default=30, ge=5, le=300)
    verify_tls: bool = True
    enabled: bool = True


class SyncSettings(BaseModel):
    interval_minutes: int = Field(default=10, ge=1, le=1440)
    dry_run: bool = True
    delta_minutes_lookback: int = Field(default=60, ge=1, le=10080)
    order_lookback_minutes: int = Field(default=120, ge=1, le=10080)


class TaxSettings(BaseModel):
    default_tax_code: str = "NON"
    gst_tax_code: str = "GST"
    hst_tax_code: str = "HST"
    pst_tax_code: str = "PST"


class CurrencyAccountSettings(BaseModel):
    cad_deposit_account: str = "Undeposited Funds CAD"
    usd_deposit_account: str = "Undeposited Funds USD"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QB_WOO_", env_nested_delimiter="__")

    database_path: Path = Path("state.db")
    log_path: Path = Path("sync.log")
    app_name: str = "QuickBooksProject"

    quickbooks: QuickBooksSettings = QuickBooksSettings()

    # Legacy single-store support
    woo: WooStoreSettings | None = None
    # Future-ready multi-store support
    woo_stores: list[WooStoreSettings] = Field(default_factory=list)

    sync: SyncSettings = SyncSettings()
    tax: TaxSettings = TaxSettings()
    currency_accounts: CurrencyAccountSettings = CurrencyAccountSettings()

    def active_stores(self) -> list[WooStoreSettings]:
        stores = [s for s in self.woo_stores if s.enabled]
        if stores:
            return stores
        if self.woo and self.woo.enabled:
            return [self.woo]
        return []


def load_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]
