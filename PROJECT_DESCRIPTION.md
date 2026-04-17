# QuickBooksProject Description

QuickBooksProject is a self-hosted Windows desktop integration that synchronizes QuickBooks Desktop Enterprise and WooCommerce.

Core goals:
- Keep QuickBooks Desktop as the authoritative inventory source.
- Push inventory updates from QuickBooks to WooCommerce by SKU.
- Import WooCommerce sales into QuickBooks as Sales Receipts.
- Provide an operator-friendly GUI for settings, diagnostics, and manual run controls.
- Support local-only deployment with SQLite state, verbose logging, and optional spreadsheet export routing.

Intended runtime:
- Windows 11 Pro / Windows Server desktop session with QuickBooks Desktop installed.
- Access to WooCommerce REST API credentials.
- No dependency on QuickBooks Online APIs or Web Connector.
