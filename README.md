# QuickBooksProject (QuickBooks Desktop ↔ WooCommerce Sync)



- ✅ Pushes QuickBooks inventory to WooCommerce by SKU.
- ✅ Picks tax code (GST / HST / PST) based on order location.
- ✅ Routes USD and CAD sales to different QuickBooks deposit accounts.
- ✅ Supports one or multiple Woo stores.

---

## Screenshots

> Note: These are architecture/UI mock screenshots included with this repo so beginners can understand the app layout quickly.

### Main GUI (dashboard)
![Main GUI dashboard](docs/screenshots/gui-dashboard.svg)

### Sync flow overview
![Sync flow overview](docs/screenshots/flow-overview.svg)

---

## 1) Prerequisites (Windows)

You should run this on the same Windows machine that can access the QuickBooks company file.

### Required software
1. **Windows 10/11 Pro** (or Windows Server desktop session).
2. **QuickBooks Desktop Enterprise** installed and licensed.
3. **Python 3.11+** installed (check "Add Python to PATH" during install).
4. A WooCommerce site with REST API access:
   - Consumer Key
   - Consumer Secret
5. A QuickBooks user/session that can authorize SDK access.

### QuickBooks SDK notes
- The app uses `pywin32` + COM (`QBXMLRP2.RequestProcessor`).
- On first use, QuickBooks will prompt to authorize the app. Approve it.
- Keep QuickBooks available during sync runs.
- QB compatibility: the app now tries multiple QBXML versions (13.0 → 12.0 → 11.0 → 10.0 → 8.0) to support more QuickBooks Enterprise releases.

---

## 2) Project structure

```text
quickbooks_project/
  app.py              # app startup wiring
  settings.py         # env settings (stores, tax, currency)
  gui.py              # PySide6 desktop GUI
  sync_engine.py      # inventory push + sales import logic
  qb_adapter.py       # QuickBooks QBXML adapter
  woo_adapter.py      # WooCommerce REST adapter
  db.py               # SQLite schema + run/order tracking
  models.py           # data models
  scheduler.py        # background scheduled jobs
  logging_config.py   # logging setup
requirements.txt
```

---

## 3) Install and run (step-by-step)

From project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

Run app:

```powershell
python -m quickbooks_project.app
```

---

## 4) Configuration for beginners

The app uses environment variables through `pydantic-settings`.

## Fastest setup: single store

Set these in your PowerShell session before launching:

```powershell
$env:QB_WOO__APP_NAME = "QuickBooksProject"
$env:QB_WOO__DATABASE_PATH = "state.db"
$env:QB_WOO__LOG_PATH = "sync.log"

$env:QB_WOO__WOO__STORE_NAME = "main-store"
$env:QB_WOO__WOO__BASE_URL = "https://yourstore.com"
$env:QB_WOO__WOO__CONSUMER_KEY = "ck_xxxxxxxxxxxxxxxxx"
$env:QB_WOO__WOO__CONSUMER_SECRET = "cs_xxxxxxxxxxxxxxxxx"
$env:QB_WOO__WOO__VERIFY_TLS = "true"

$env:QB_WOO__SYNC__DRY_RUN = "true"
$env:QB_WOO__SYNC__INTERVAL_MINUTES = "10"
$env:QB_WOO__SYNC__DELTA_MINUTES_LOOKBACK = "60"
$env:QB_WOO__SYNC__ORDER_LOOKBACK_MINUTES = "120"

$env:QB_WOO__TAX__DEFAULT_TAX_CODE = "NON"
$env:QB_WOO__TAX__DEFAULT_TAX_NAME = "No Tax"
$env:QB_WOO__TAX__DEFAULT_TAX_RATE_PERCENT = "0"
$env:QB_WOO__TAX__TAX_RULES = '[{"country":"CA","state":"ON","tax_code":"HST","tax_name":"HST","rate_percent":13.0},{"country":"CA","state":"*","tax_code":"GST","tax_name":"GST","rate_percent":5.0}]'

$env:QB_WOO__CURRENCY_ACCOUNTS__DEFAULT_DEPOSIT_ACCOUNT = "Undeposited Funds CAD"
$env:QB_WOO__CURRENCY_ACCOUNTS__ROUTES = '[{"currency":"CAD","deposit_account":"Undeposited Funds CAD"},{"currency":"USD","deposit_account":"Undeposited Funds USD"}]'

$env:QB_WOO__HOST_SETUP__AUTO_CONFIGURE_WINDOWS_FIREWALL = "false"
$env:QB_WOO__HOST_SETUP__FIREWALL_RULE_NAME = "QuickBooksProject Outbound 443"
```

Then run:

```powershell
python -m quickbooks_project.app
```

Optional advanced customization via environment variables:

```powershell
$env:QB_WOO__TAX__TAX_RULES = '[{"country":"CA","state":"ON","tax_code":"HST","tax_name":"HST","rate_percent":13.0},{"country":"CA","state":"*","tax_code":"GST","tax_name":"GST","rate_percent":5.0}]'
$env:QB_WOO__CURRENCY_ACCOUNTS__ROUTES = '[{"currency":"CAD","deposit_account":"Undeposited Funds CAD"},{"currency":"USD","deposit_account":"Undeposited Funds USD"}]'
$env:QB_WOO__CURRENCY_ACCOUNTS__DEFAULT_DEPOSIT_ACCOUNT = "Undeposited Funds CAD"
```

## Multi-store setup (future-ready)

Use `QB_WOO__WOO_STORES` as a JSON array:

```powershell
$env:QB_WOO__WOO_STORES = '[
  {
    "store_name": "store-ca",
    "base_url": "https://store-ca.example.com",
    "consumer_key": "ck_xxx",
    "consumer_secret": "cs_xxx",
    "enabled": true
  },
  {
    "store_name": "store-us",
    "base_url": "https://store-us.example.com",
    "consumer_key": "ck_yyy",
    "consumer_secret": "cs_yyy",
    "enabled": true
  }
]'
```

If `WOO_STORES` is present and enabled, it is used. Otherwise the app falls back to single `WOO` settings.

---

## 5) How syncing works

## A) Inventory sync (QuickBooks → Woo)
1. App reads inventory quantities from QuickBooks.
2. For each SKU, app finds Woo product/variation.
3. If quantity differs, updates Woo stock.
4. Logs per-item outcome in SQLite.

This keeps **QuickBooks authoritative**.

## B) Sales import (Woo → QuickBooks)
1. App pulls recent Woo orders with status `processing` or `completed`.
2. Skips orders already processed (idempotency table).
3. Decides tax code by country/province.
4. Decides deposit account by currency (USD/CAD).
5. Posts a QuickBooks Sales Receipt.

Posting Sales Receipts is how inventory is reduced in QuickBooks for inventory-tracked items.

---

## 6) GUI walkthrough

Buttons in the main window:

- **Test Connections**
  - Checks QuickBooks COM connection and each Woo store API connection.
- **Run Inventory Full Sync**
  - Pushes full inventory snapshot from QB to Woo.
- **Run Inventory Delta Sync**
  - Pushes only recently changed QB items.
- **Import Woo Sales → QuickBooks**
  - Pulls orders and posts Sales Receipts in QB.
- **Pause Scheduler**
  - Stops/resumes scheduled background jobs.
- **Settings tab**
  - Explicit fields for Woo API keys, URL, tax codes, deposit accounts, and QBXML versions.
  - Validation highlights invalid fields and shows exactly what to fix.

Use **Dry run** first.

---

## 7) SQLite database files and tables

By default, SQLite is `state.db` with tables:

- `sync_runs` — each sync/import run summary.
- `sync_items` — per-item inventory outcomes.
- `processed_orders` — Woo order idempotency and posting status.
- `sku_map` — optional SKU mapping storage.
- `settings` — optional key/value settings.

---

## 8) Taxes and currency routing

Tax logic is now fully customizable using rule lists (GUI or env settings):

- `tax.default_tax_code` / `tax.default_tax_name` / `tax.default_tax_rate_percent`
- `tax.tax_rules[]` with per-country/per-state rules, each containing:
  - `country`, `state` (`*` supported), `tax_code`, `tax_name`, `rate_percent`

Currency routing is also fully customizable:

- `currency_accounts.default_deposit_account`
- `currency_accounts.routes[]` entries containing:
  - `currency`, `deposit_account`

GUI Settings tab supports editing both via JSON fields with validation errors tied to the exact field.

> Important: Verify tax codes and account names exactly match your QuickBooks company file.

---

## 9) Beginner deployment checklist

1. Start with one Woo store.
2. Turn on `DRY_RUN=true`.
3. Click **Test Connections**.
4. Run **Inventory Full Sync** in dry run and check logs.
5. Run **Import Woo Sales → QuickBooks** in dry run.
6. Validate expected mappings and tax/account behavior.
7. Turn off dry run for live writes.
8. Let scheduler run and monitor `sync.log` + `state.db`.

---

## 10) Troubleshooting

## "No WooCommerce stores configured"
Set either:
- single-store env vars (`QB_WOO__WOO__...`) or
- `QB_WOO__WOO_STORES` JSON.

## QuickBooks COM errors
- Run app under a Windows user with QB access.
- Open QuickBooks and company file once interactively.
- Re-check QuickBooks SDK app authorization.

## Woo API 401/403
- Verify Consumer Key/Secret.
- Ensure REST API permissions include read/write.
- Ensure HTTPS base URL and valid certificate.

## SKU not found
- Ensure Woo SKU and QB SKU use exact same string.
- For variable products, SKU must exist on the variation if syncing variation stock.

---

## 11) Security recommendations

- Use a dedicated Woo API user with least privilege.
- Do not hardcode credentials in source code.
- Rotate API keys regularly.
- Restrict access to `state.db` and `sync.log`.

---

## 12) What to improve next

- Per-store tax rules loaded from config file/database.
- More complete QB item mapping (`ListID` cache and lookup fallback).
- Better GUI settings editor (save/load without env vars).
- Unit tests with adapter mocks.
- Optional webhook-triggered order sync for near-real-time posting.

---

## 13) Quick start command recap

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# set QB_WOO__... env vars
python -m quickbooks_project.app
```

---

## 14) Self-hosted / no Intuit services

If you want this fully self-hosted (no Intuit cloud services), see `SELF_HOSTED_DEPLOYMENT.md`.


---

## 15) Modern UX + Operability Improvements

Recent updates added:
- modernized visual styling in the desktop GUI,
- hover help badges (?) for settings labels,
- verbose error dialogs with technical details,
- rotating verbose log files for easier diagnostics.

These improvements align with common strengths seen in well-reviewed open-source inventory tools (strong tracking/auditability, explicit settings, and actionable error feedback).

---


## 16) Woo Field Sync + Spreadsheet Routing

The Settings tab now supports optional Woo order field export to spreadsheet:

- `Spreadsheet export enabled` (`true`/`false`)
- `Workbook path` (e.g. `woo_sync_export.xlsx`)
- `Worksheet name` (tab name inside workbook)
- `Spreadsheet field routes JSON` (map Woo fields to target columns)

Example route JSON:

```json
[
  {"woo_field":"id","target_column":"OrderID","enabled":true},
  {"woo_field":"billing.email","target_column":"CustomerEmail","enabled":true},
  {"woo_field":"total","target_column":"OrderTotal","enabled":true}
]
```

Available Woo fields are shown directly in the Settings tab UI and validated before save/apply.

---

## 17) Exactly what to configure in QuickBooks Desktop

Before running the app live, do this in QuickBooks Desktop Enterprise:

1. **Company file & user access**
   - Open the target company file on the same Windows machine where this app will run.
   - Use a QuickBooks user with permissions to:
     - read inventory items,
     - create Sales Receipts,
     - access the chart of accounts and tax items.

2. **SDK authorization**
   - On first app connection, QuickBooks should show an SDK authorization prompt.
   - Approve access for this app and allow it to sign in automatically when safe for your environment.

3. **Inventory item setup**
   - Ensure inventory items are enabled and quantities are tracked.
   - Ensure each item has a stable SKU or identifier that maps to Woo SKU.
   - If using `ManufacturerPartNumber` for SKU mapping, verify it is populated consistently.

4. **Tax items/codes**
   - Create/verify the tax codes used in app settings (e.g., `GST`, `HST`, `PST`, `NON`).
   - Ensure the exact names in settings match QuickBooks names.

5. **Deposit accounts for currency routing**
   - Create/verify accounts for CAD/USD routing (or your desired account names).
   - Ensure account names match exactly what you configure in the app.

6. **Operational behavior**
   - Keep QuickBooks installed, licensed, and accessible during sync windows.
   - If QuickBooks is closed/locked, COM requests can fail.

---

## 18) Exactly what to configure in WordPress / WooCommerce

1. **WooCommerce REST API credentials**
   - Generate Consumer Key + Consumer Secret with read/write permissions.
   - Use HTTPS store URL.

2. **SKU discipline**
   - Ensure each product (and variation if used) has correct SKU.
   - Avoid duplicate SKUs across products/variations.

3. **Stock settings**
   - Ensure products are configured to manage stock if you want quantity updates reflected.

4. **Order flow readiness**
   - Sales import logic reads Woo orders (processing/completed) and posts them to QB.
   - Validate your Woo order statuses and payment lifecycle match this expectation.

5. **Plugins / environment**
   - Required: WooCommerce itself (REST API is built-in).
   - No mandatory third-party Woo sync plugin is required for this project.
   - If security plugins/firewalls are enabled, allow API requests from the app host.

---

## 19) SQLite prerequisites and operational notes

SQLite is bundled with Python (`sqlite3`) and generally requires no separate install.

1. **Filesystem permissions**
   - The app process account must have read/write access to the folder containing `state.db`.

2. **Backups**
   - Back up `state.db` regularly (daily recommended for operations).
   - Also back up logs for diagnostics.

3. **Concurrency**
   - SQLite is fine for single-host/single-app MVP usage.
   - For high concurrency or multi-operator writes, migrate state to Postgres in a future version.

4. **Idempotency**
   - `processed_orders` table prevents duplicate posting of the same order.

---

## 20) Critical oversights checklist before go-live

- [ ] Test with `dry_run=true` first.
- [ ] Confirm all QuickBooks tax/account names exactly match settings.
- [ ] Confirm Woo SKU coverage and no duplicates.
- [ ] Validate one end-to-end order import in a test company file first.
- [ ] Validate spreadsheet routing output (if enabled) and header/column mapping.
- [ ] Keep a rollback plan (DB backup + app settings snapshot).
- [ ] Define who monitors failures and where alerts/logs are reviewed.

---

## 21) Section 12 roadmap follow-up

The roadmap items remain valid and are now prioritized as:

1. Per-store tax rules loaded from config/database (beyond current JSON settings model).
2. More complete QB item mapping (`ListID` cache + fallback lookup).
3. Full persistent GUI settings editor (save/load securely without manual env setup).
4. Unit/integration tests with adapter mocks and sample payloads.
5. Optional webhook-triggered near-real-time order sync.

---

## 22) Ports, permissions, and communication channels (automatic host prep)

The app now includes a **Prepare Host (Ports/Permissions)** workflow in the GUI.

What it checks/configures:

1. **Filesystem permissions**
   - Verifies the app can write to the directories used by:
     - `state.db`
     - `sync.log`

2. **Network connectivity to Woo stores**
   - Tests TCP connectivity to each configured Woo store host/port (typically 443 for HTTPS).

3. **Windows firewall rule (optional)**
   - If enabled in settings (`host_setup.auto_configure_windows_firewall=true`), app attempts to create outbound TCP 443 allow rule.
   - This may require running with Administrator privileges.

Important notes:
- This feature does **not** bypass OS security; it reports errors when elevation is required.
- If firewall rule creation fails, run the app elevated once or create rule manually.
- If your environment uses proxy/security appliances, coordinate with IT to allow the QuickBooks host to reach your Woo API endpoint(s).

---

## 23) Windows 11 Pro installer build (guided setup launcher)

This repository now includes installer tooling:

- Inno Setup script: `installer/QuickBooksProject.iss`
- Build script: `scripts/build_windows_installer.ps1`

Build steps on Windows 11 Pro:

1. Install Python 3.11+.
2. Install Inno Setup 6.
3. Run PowerShell as Administrator.
4. Execute:

```powershell
./scripts/build_windows_installer.ps1
```

Outputs:
- App EXE from PyInstaller in `dist/app` (or PyInstaller default dist path).
- Installer EXE in `dist/installer`.

Installer behavior:
- Creates Start Menu/Desktop entries.
- Launches app with `--first-run` so setup opens directly to Settings tab.

---

## 24) GitHub publication notes

To publish publicly:

1. Push this branch to your GitHub repository.
2. In GitHub repository settings, set visibility to **Public**.
3. Create a release and attach installer from `dist/installer`.

> This coding environment cannot directly change your GitHub repo visibility settings without your account/token context.

---

## 25) Migrating this codebase to your `quickbooks-connector` GitHub repo

If you already created a GitHub repo named `quickbooks-connector`, migrate this project with:

```bash
git remote rename origin old-origin || true
git remote add origin https://github.com/<your-org-or-user>/quickbooks-connector.git
git push -u origin --all
git push -u origin --tags
```

Optional cleanup after successful migration:

```bash
git remote remove old-origin
```

Set repository visibility to public in GitHub settings, then create a release and upload the installer artifact from `dist/installer`.
