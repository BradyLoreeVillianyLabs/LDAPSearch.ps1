# QuickBooksProject: Fully Self-Hosted / No Intuit Cloud Services

Yes — this project can run **without Intuit cloud services**.

The current implementation already uses:
- **QuickBooks Desktop SDK via local COM/QBXML** (`pywin32`) on your Windows machine.
- **WooCommerce REST API** directly against your WordPress server.
- **Local SQLite** for state/logs.

No QuickBooks Online API, no Web Connector, and no Intuit-hosted middleware are required.

---

## What “No Intuit Services” means in practice

You can operate with:
1. Your own QuickBooks Desktop installation (local company file).
2. Your own WordPress/WooCommerce hosting.
3. Your own Windows service/scheduler for the sync app.
4. Your own logging/monitoring/backup stack.

The only external dependency left is your own infrastructure (and WooCommerce host), not Intuit cloud APIs.

---

## Self-hosted architecture (recommended)

1. **Windows QuickBooks host**
   - Runs QuickBooks Desktop + `quickbooks_project` app.
   - Has direct access to company file.

2. **Your WooCommerce host**
   - WordPress + WooCommerce REST API.

3. **Optional self-hosted integration API**
   - Small API (FastAPI/Flask) you host to receive Woo webhooks and queue them.
   - `quickbooks_project` polls this queue to post to QuickBooks.
   - Useful if you want near-real-time behavior without relying on polling windows.

4. **Self-hosted observability**
   - Ship logs to Loki/ELK/Graylog, or keep local with backup rotation.

---

## What to disable/avoid to stay fully self-hosted

- Do **not** use QuickBooks Web Connector.
- Do **not** use QuickBooks Online API.
- Do **not** use third-party iPaaS connectors unless hosted by you.
- Do **not** rely on SaaS webhook relays if your policy requires fully internal routing.

---

## Security hardening checklist

- Restrict Woo API keys by role/capabilities.
- Allowlist outbound traffic only to your Woo host.
- Protect the Windows account running QuickBooks + sync app.
- Encrypt secrets at rest (Windows Credential Manager preferred).
- Back up `state.db` and log files regularly.
- Use HTTPS/TLS on Woo endpoints and internal APIs.

---

## Reliability hardening checklist

- Run app under Windows Task Scheduler / NSSM service wrapper.
- Enable dry-run first, then live mode.
- Use idempotency (`processed_orders`) to prevent double posting.
- Keep retry/backoff enabled for Woo requests.
- Add healthcheck + alerting (email/Slack/Teams or on-prem equivalent).

---

## Data ownership and compliance

With this model, your business data remains under your control:
- Inventory/accounting logic stays in your QuickBooks Desktop company file.
- Order and product data stays in WooCommerce DB + your backups.
- Integration state stays in your local SQLite DB (or future self-hosted Postgres).

---

## Optional next step: move from SQLite to self-hosted Postgres

For multi-store and higher volume, migrate state from SQLite to Postgres hosted by you:
- Better concurrency and observability.
- Easier backups/replication.
- Cleaner long-term multi-operator operations.

---

## Bottom line

**Yes, this can be run fully self-hosted with zero Intuit cloud services.**
The existing code path already aligns with that model because it talks directly to local QuickBooks Desktop COM and your WooCommerce endpoints.
