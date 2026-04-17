from __future__ import annotations

import os
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .settings import AppSettings


@dataclass(slots=True)
class HostSetupResult:
    ok: bool
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class HostSetupManager:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def prepare(self) -> HostSetupResult:
        result = HostSetupResult(ok=True)

        self._check_local_paths(result)
        self._check_store_connectivity(result)

        if os.name == "nt" and self.settings.host_setup.auto_configure_windows_firewall:
            self._configure_windows_firewall(result)

        if result.errors:
            result.ok = False
        return result

    def _check_local_paths(self, result: HostSetupResult) -> None:
        for p in [self.settings.database_path, self.settings.log_path]:
            parent = Path(p).resolve().parent
            try:
                parent.mkdir(parents=True, exist_ok=True)
                probe = parent / ".qb_project_write_test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                result.actions.append(f"Write permission verified: {parent}")
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"Cannot write to required directory '{parent}': {exc}")

    def _check_store_connectivity(self, result: HostSetupResult) -> None:
        stores = self.settings.active_stores()
        timeout = self.settings.host_setup.test_timeout_seconds
        for store in stores:
            parsed = urlparse(str(store.base_url))
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if not host:
                result.errors.append(f"Invalid store URL for '{store.store_name}': {store.base_url}")
                continue
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    result.actions.append(f"Connectivity OK: {store.store_name} -> {host}:{port}")
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(
                    f"Could not reach {store.store_name} ({host}:{port}). Check firewall/proxy/network. Detail: {exc}"
                )

    def _configure_windows_firewall(self, result: HostSetupResult) -> None:
        rule_name = self.settings.host_setup.firewall_rule_name
        check_cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue | Select-Object -First 1",
        ]
        add_cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"New-NetFirewallRule -DisplayName '{rule_name}' "
                "-Direction Outbound -Action Allow -Protocol TCP -RemotePort 443"
            ),
        ]
        try:
            check = subprocess.run(check_cmd, capture_output=True, text=True, check=False)
            if check.returncode == 0 and check.stdout.strip():
                result.actions.append(f"Firewall rule already present: {rule_name}")
                return

            add = subprocess.run(add_cmd, capture_output=True, text=True, check=False)
            if add.returncode == 0:
                result.actions.append(f"Firewall rule created: {rule_name}")
            else:
                result.errors.append(
                    f"Failed to create firewall rule '{rule_name}'. Run as Administrator. {add.stderr.strip()}"
                )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Firewall configuration failed: {exc}")
