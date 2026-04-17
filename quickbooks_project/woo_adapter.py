from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import OrderLine, WooOrder, WooProductRef
from .settings import WooStoreSettings

LOGGER = logging.getLogger(__name__)


class WooAdapter:
    def __init__(self, settings: WooStoreSettings) -> None:
        self.settings = settings
        self.store_name = settings.store_name
        self.session = requests.Session()
        self.session.auth = (settings.consumer_key, settings.consumer_secret)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        base = str(self.settings.base_url).rstrip("/")
        return f"{base}{path}"

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = self.session.request(
            method,
            self._url(path),
            timeout=self.settings.timeout_seconds,
            verify=self.settings.verify_tls,
            **kwargs,
        )
        response.raise_for_status()
        return response


    def reconfigure(self, settings: WooStoreSettings) -> None:
        self.settings = settings
        self.store_name = settings.store_name
        self.session.auth = (settings.consumer_key, settings.consumer_secret)

    def test_connection(self) -> bool:
        resp = self._request("GET", "/wp-json/wc/v3/system_status")
        return resp.status_code == 200

    def find_by_sku(self, sku: str) -> WooProductRef | None:
        encoded = quote_plus(sku)
        response = self._request("GET", f"/wp-json/wc/v3/products?sku={encoded}")
        products = response.json()
        if not products:
            return None
        if len(products) > 1:
            raise ValueError(f"[{self.store_name}] Duplicate WooCommerce SKU conflict for '{sku}'")
        product = products[0]

        if product.get("type") == "variable":
            variation = self._find_variation_by_sku(product_id=product["id"], sku=sku)
            if variation:
                return WooProductRef(
                    sku=sku,
                    product_id=product["id"],
                    variation_id=variation["id"],
                    stock_quantity=variation.get("stock_quantity"),
                    raw=variation,
                )

        return WooProductRef(
            sku=sku,
            product_id=product["id"],
            variation_id=None,
            stock_quantity=product.get("stock_quantity"),
            raw=product,
        )

    def _find_variation_by_sku(self, product_id: int, sku: str) -> dict[str, Any] | None:
        encoded = quote_plus(sku)
        response = self._request("GET", f"/wp-json/wc/v3/products/{product_id}/variations?sku={encoded}")
        variations = response.json()
        if not variations:
            return None
        if len(variations) > 1:
            raise ValueError(f"[{self.store_name}] Duplicate variation SKU conflict for '{sku}'")
        return variations[0]

    def update_stock(self, ref: WooProductRef, quantity: int) -> dict[str, Any]:
        payload = {"manage_stock": True, "stock_quantity": int(quantity)}
        if ref.variation_id:
            path = f"/wp-json/wc/v3/products/{ref.product_id}/variations/{ref.variation_id}"
        elif ref.product_id:
            path = f"/wp-json/wc/v3/products/{ref.product_id}"
        else:
            raise ValueError("Cannot update stock without product reference")
        response = self._request("PUT", path, json=payload)
        LOGGER.info("[%s] Updated SKU=%s to quantity=%s", self.store_name, ref.sku, quantity)
        return response.json()

    def fetch_recent_orders(self, minutes_lookback: int = 120) -> list[WooOrder]:
        after_ts = datetime.now(timezone.utc).timestamp() - (minutes_lookback * 60)
        after_iso = datetime.fromtimestamp(after_ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        path = f"/wp-json/wc/v3/orders?status=processing,completed&after={quote_plus(after_iso)}&per_page=100"
        response = self._request("GET", path)
        rows = response.json()
        orders: list[WooOrder] = []
        for row in rows:
            billing = row.get("billing") or {}
            line_items = row.get("line_items") or []
            lines = [
                OrderLine(
                    sku=(li.get("sku") or "").strip(),
                    quantity=int(li.get("quantity") or 0),
                    unit_price=float(li.get("price") or 0),
                    line_total=float(li.get("total") or 0),
                )
                for li in line_items
                if (li.get("sku") or "").strip()
            ]
            created_raw = row.get("date_created_gmt") or row.get("date_created")
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            orders.append(
                WooOrder(
                    store_name=self.store_name,
                    order_id=str(row["id"]),
                    created_at=created_at,
                    currency=(row.get("currency") or "").upper(),
                    country=(billing.get("country") or "").upper(),
                    state=(billing.get("state") or "").upper(),
                    city=billing.get("city") or "",
                    email=billing.get("email") or "",
                    lines=lines,
                    total_tax=float(row.get("total_tax") or 0),
                    total_amount=float(row.get("total") or 0),
                    raw=row,
                )
            )
        LOGGER.info("[%s] Pulled %s WooCommerce orders", self.store_name, len(orders))
        return orders
