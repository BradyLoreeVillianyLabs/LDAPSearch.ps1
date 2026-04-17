# QuickBooks Enterprise 2024 ↔ WooCommerce Inventory Sync (Python + GUI)

## Goal
Use **QuickBooks Enterprise 2024 on Windows 11 Pro** as the **authoritative inventory source**, and sync stock levels (and optionally prices) to WooCommerce without using QuickBooks Web Connector.

## Recommended Architecture
1. **Desktop app (Python GUI)** runs on the QuickBooks server desktop.
2. App reads inventory from QuickBooks via **QuickBooks Desktop SDK (qbXML / QBFC COM API)**.
3. App writes inventory to WooCommerce via **WooCommerce REST API**.
4. App stores sync state locally in **SQLite** (last run timestamp, SKU mapping, sync logs, retry queue).
5. App schedules automatic jobs (every X minutes) and supports manual sync.

## Why this fits your constraints
- No Web Connector dependency.
- QuickBooks Enterprise stays source of truth.
- Python stack supports both COM integration and a desktop GUI.

## Core Components

### 1) QuickBooks Adapter (`qb_adapter.py`)
- Connect to QuickBooks Desktop company file through SDK.
- Pull inventory items: `ListID`, `FullName`, `ManufacturerPartNumber` or custom SKU field, quantity on hand.
- Normalize into internal records:
  - `sku`
  - `qty_on_hand`
  - `item_ref`
  - `last_modified`

### 2) WooCommerce Adapter (`woo_adapter.py`)
- Auth via consumer key/secret over HTTPS.
- Resolve products by SKU (`/wp-json/wc/v3/products?sku=...`).
- Update `stock_quantity`, `manage_stock=true`, optionally `regular_price`.
- Handle variable products by syncing variation SKUs when applicable.

### 3) Sync Engine (`sync_engine.py`)
- Direction: **QuickBooks → WooCommerce**.
- For each SKU from QuickBooks:
  - Find matching Woo product/variation by SKU.
  - Compare quantity and update only when changed.
- Record outcome per SKU (success/failure/no-op).
- Retry transient API failures with backoff.

### 4) Local Data (`state.db`)
Suggested tables:
- `sync_runs(id, started_at, ended_at, status, summary_json)`
- `sync_items(run_id, sku, qb_qty, woo_qty_before, woo_qty_after, result, error)`
- `sku_map(qb_item_ref, sku, woo_product_id, woo_variation_id)`
- `settings(key, value)`

### 5) GUI (`gui.py`)
Good options:
- **PySide6** (modern native-feeling app)
- Tkinter (simple, built-in)

Suggested GUI screens:
- Connection Settings (QB company file context + Woo API credentials)
- SKU Mapping
- Sync Dashboard (last run, next run, changed items)
- Logs/Error panel
- Buttons: `Test Connections`, `Run Full Sync`, `Run Delta Sync`, `Pause Scheduler`

## Recommended Tech Stack
- Python 3.11+
- `pywin32` (COM calls into QuickBooks Desktop SDK)
- `requests` (WooCommerce REST)
- `pydantic` (validation)
- `SQLAlchemy` or `sqlite3`
- `APScheduler` (interval scheduling)
- `PySide6` (GUI)
- `tenacity` (retry logic)

## Data & Mapping Rules (important)
1. **SKU is the primary key across systems**.
2. If a QuickBooks item has no SKU, flag it for manual mapping.
3. If multiple Woo products share a SKU, mark conflict and skip.
4. If Woo product is out of stock but QB has stock, QB value wins.
5. Optionally support warehouse/location logic later; start with single stock field.

## Security & Reliability
- Store Woo API keys encrypted (Windows Credential Manager or encrypted local config).
- Use least-privilege Woo API user.
- Keep full audit logs for each sync run.
- Add dry-run mode before enabling live writes.
- Add lockfile to prevent concurrent sync jobs.

## Implementation Phases

### Phase 1: Connectivity + Read-only validation
- Connect to QuickBooks and list inventory with SKUs.
- Connect to WooCommerce and fetch products by SKU.
- Show side-by-side preview in GUI.

### Phase 2: One-way inventory sync
- Update Woo stock quantity from QuickBooks.
- Add per-item logging and retry.
- Add manual full sync button.

### Phase 3: Scheduler + operations hardening
- Add background interval sync.
- Add conflict queue and error handling workflow.
- Add dashboard metrics and email/Slack alerts (optional).

## Operational Notes for QuickBooks Desktop
- Run the app under a Windows account that has QuickBooks company file access.
- Keep QuickBooks company file available during scheduled runs.
- Initial SDK authorization prompt in QuickBooks must be approved for the app.
- In production, run app always-on (or as a signed service wrapper) on the same machine where QuickBooks is accessible.

## Suggested Project Layout
```text
quickbooks_project/
  app.py
  gui.py
  sync_engine.py
  qb_adapter.py
  woo_adapter.py
  models.py
  settings.py
  db.py
  scheduler.py
  logging_config.py
  requirements.txt
```

## MVP Acceptance Criteria
- Test connections succeed for QuickBooks and WooCommerce.
- At least 95% of active SKUs map automatically by SKU.
- Manual sync updates Woo inventory for changed QB items only.
- Sync run report shows successes, skips, failures with reasons.
- Recoverable failures retry automatically and are visible in GUI.

## Extended Requirements Implemented (v2)
- Added **WooCommerce → QuickBooks sales import** flow that posts Woo orders to QuickBooks as Sales Receipts.
- Added **tax decision logic** by shipping/billing location to select GST/HST/PST tax codes.
- Added **currency routing** so USD and CAD sales post to separate QuickBooks deposit accounts.
- Preserved **QuickBooks as inventory authority** by keeping QuickBooks-driven inventory pushes to Woo stores.
- Added **multi-store foundation**: app can manage multiple Woo stores and sync each against one QuickBooks company file.
