from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import win32com.client

from .models import InventoryItem, TaxDecision, WooOrder

LOGGER = logging.getLogger(__name__)


class QuickBooksAdapter:
    """QuickBooks Desktop adapter via QBXML RequestProcessor COM.

    Supports fallback QBXML versions to improve compatibility across
    different QuickBooks Enterprise releases.
    """

    def __init__(
        self,
        app_id: str = "",
        app_name: str = "QuickBooksProject",
        qbxml_versions: list[str] | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_name = app_name
        self.qbxml_versions = qbxml_versions or ["13.0", "12.0", "11.0", "10.0", "8.0"]
        self._processor: Any | None = None
        self._ticket: str | None = None

    def open(self) -> None:
        if self._processor is not None:
            return
        processor = win32com.client.Dispatch("QBXMLRP2.RequestProcessor")
        processor.OpenConnection2(self.app_id, self.app_name, 1)
        ticket = processor.BeginSession("", 2)
        self._processor = processor
        self._ticket = ticket
        LOGGER.info("QuickBooks session opened")

    def close(self) -> None:
        if self._processor is None:
            return
        if self._ticket:
            self._processor.EndSession(self._ticket)
        self._processor.CloseConnection()
        self._processor = None
        self._ticket = None
        LOGGER.info("QuickBooks session closed")

    def __enter__(self) -> "QuickBooksAdapter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        self.close()

    def test_connection(self) -> bool:
        self.open()
        _ = self.fetch_inventory_items(modified_since=None)
        return True

    def fetch_inventory_items(self, modified_since: datetime | None = None) -> list[InventoryItem]:
        self.open()
        request_xml_templates = [self._build_inventory_query(version=v, modified_since=modified_since) for v in self.qbxml_versions]
        response_xml = self._process_request_with_fallback(request_xml_templates)
        return self._parse_inventory_response(response_xml)

    def record_sales_receipt(
        self,
        order: WooOrder,
        tax: TaxDecision,
        deposit_to_account: str,
        dry_run: bool = False,
    ) -> str:
        self.open()

        request_xml_templates = [
            self._build_sales_receipt_request(version=v, order=order, tax=tax, deposit_to_account=deposit_to_account)
            for v in self.qbxml_versions
        ]

        if dry_run:
            LOGGER.info("Dry-run enabled; skipping SalesReceiptAdd for Woo order %s", order.order_id)
            return f"dry-run-{order.order_id}"

        response_xml = self._process_request_with_fallback(request_xml_templates)
        txn_id = self._extract_tag(response_xml, "TxnID")
        if not txn_id:
            raise RuntimeError(f"QuickBooks did not return TxnID for Woo order {order.order_id}")
        LOGGER.info("Recorded Woo order %s as QuickBooks SalesReceipt TxnID=%s", order.order_id, txn_id)
        return txn_id

    def _process_request_with_fallback(self, request_xml_templates: list[str]) -> str:
        assert self._processor is not None
        assert self._ticket is not None

        last_exc: Exception | None = None
        for version, xml in zip(self.qbxml_versions, request_xml_templates, strict=False):
            try:
                response_xml = self._processor.ProcessRequest(self._ticket, xml)
                LOGGER.debug("QBXML request succeeded with version %s", version)
                return response_xml
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                LOGGER.warning("QBXML version %s failed, trying next fallback: %s", version, exc)

        raise RuntimeError(f"All QBXML versions failed: {self.qbxml_versions}") from last_exc

    def _build_inventory_query(self, version: str, modified_since: datetime | None = None) -> str:
        modified_filter = ""
        if modified_since:
            modified_filter = f"<FromModifiedDate>{modified_since.isoformat()}</FromModifiedDate>"
        return f"""
<?xml version=\"1.0\"?>
<?qbxml version=\"{version}\"?>
<QBXML>
  <QBXMLMsgsRq onError=\"continueOnError\">
    <ItemInventoryQueryRq requestID=\"1\">
      <OwnerID>0</OwnerID>
      {modified_filter}
      <IncludeRetElement>ListID</IncludeRetElement>
      <IncludeRetElement>Name</IncludeRetElement>
      <IncludeRetElement>ManufacturerPartNumber</IncludeRetElement>
      <IncludeRetElement>QuantityOnHand</IncludeRetElement>
      <IncludeRetElement>TimeModified</IncludeRetElement>
    </ItemInventoryQueryRq>
  </QBXMLMsgsRq>
</QBXML>
""".strip()

    def _build_sales_receipt_request(self, version: str, order: WooOrder, tax: TaxDecision, deposit_to_account: str) -> str:
        line_xml = "\n".join(
            f"""
      <SalesReceiptLineAdd>
        <ItemRef><FullName>{self._xml_escape(line.sku)}</FullName></ItemRef>
        <Desc>Woo Order {self._xml_escape(order.order_id)} ({self._xml_escape(order.store_name)})</Desc>
        <Quantity>{line.quantity}</Quantity>
        <Rate>{line.unit_price:.2f}</Rate>
      </SalesReceiptLineAdd>
            """.strip()
            for line in order.lines
        )

        return f"""
<?xml version=\"1.0\"?>
<?qbxml version=\"{version}\"?>
<QBXML>
  <QBXMLMsgsRq onError=\"stopOnError\">
    <SalesReceiptAddRq requestID=\"woo-{self._xml_escape(order.order_id)}\">
      <SalesReceiptAdd>
        <RefNumber>WOO-{self._xml_escape(order.store_name)}-{self._xml_escape(order.order_id)}</RefNumber>
        <TxnDate>{order.created_at.date().isoformat()}</TxnDate>
        <Memo>Woo order {self._xml_escape(order.order_id)} | {self._xml_escape(order.store_name)} | {order.currency}</Memo>
        <DepositToAccountRef><FullName>{self._xml_escape(deposit_to_account)}</FullName></DepositToAccountRef>
        <ItemSalesTaxRef><FullName>{self._xml_escape(tax.tax_code)}</FullName></ItemSalesTaxRef>
        {line_xml}
      </SalesReceiptAdd>
    </SalesReceiptAddRq>
  </QBXMLMsgsRq>
</QBXML>
""".strip()

    def _parse_inventory_response(self, response_xml: str) -> list[InventoryItem]:
        items: list[InventoryItem] = []
        chunks = response_xml.split("<ItemInventoryRet>")
        for chunk in chunks[1:]:
            body = chunk.split("</ItemInventoryRet>")[0]
            list_id = self._extract_tag(body, "ListID")
            name = self._extract_tag(body, "Name")
            mpn = self._extract_tag(body, "ManufacturerPartNumber")
            qty_raw = self._extract_tag(body, "QuantityOnHand")
            modified_raw = self._extract_tag(body, "TimeModified")
            sku = (mpn or name).strip()
            if not sku:
                continue
            qty = int(float(qty_raw or "0"))
            modified = None
            if modified_raw:
                modified = datetime.fromisoformat(modified_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            items.append(
                InventoryItem(
                    sku=sku,
                    qty_on_hand=qty,
                    item_ref=list_id,
                    last_modified=modified,
                )
            )
        LOGGER.info("Fetched %s inventory items from QuickBooks", len(items))
        return items

    @staticmethod
    def _extract_tag(text: str, tag: str) -> str:
        start = f"<{tag}>"
        end = f"</{tag}>"
        if start not in text or end not in text:
            return ""
        return text.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0].strip()

    @staticmethod
    def _xml_escape(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
