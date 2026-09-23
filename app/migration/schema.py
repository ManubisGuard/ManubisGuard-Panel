from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# Tables which are part of the durable account/configuration graph. High-volume
# telemetry is deliberately separated because it should not block a migration
# when the source backup does not contain historical metrics.
CORE_TABLES: tuple[str, ...] = (
    "admin_roles",
    "admins",
    "users",
    "user_templates",
    "next_plans",
    "groups",
    "inbounds",
    "core_configs",
    "hosts",
    "nodes",
    "settings",
)

RELATION_TABLES: tuple[str, ...] = (
    "users_groups_association",
    "inbounds_groups_association",
    "template_group_association",
)

OPTIONAL_TABLES: tuple[str, ...] = (
    "api_keys",
    "notification_reminders",
    "admin_notification_reminders",
    "user_hwids",
    "user_subscription_updates",
    "wireguard_subnets",
    "client_templates",
)

TELEMETRY_TABLES: tuple[str, ...] = (
    "node_usages",
    "node_user_usages",
    "node_usage_reset_logs",
    "admin_usage_logs",
    "user_usage_reset_logs",
    "node_stats",
)

@dataclass(frozen=True)
class TableInventory:
    present: tuple[str, ...]
    missing_core: tuple[str, ...]
    missing_optional: tuple[str, ...]
    telemetry_present: tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return not self.missing_core


def build_inventory(table_names: Iterable[str]) -> TableInventory:
    names = {str(name) for name in table_names}
    return TableInventory(
        present=tuple(sorted(names)),
        missing_core=tuple(sorted(set(CORE_TABLES) - names)),
        missing_optional=tuple(sorted(set(OPTIONAL_TABLES) - names)),
        telemetry_present=tuple(sorted(set(TELEMETRY_TABLES) & names)),
    )


# Legacy PasarGuard data can be imported even when its backup predates newer
# optional tables. Required fields are handled by the adapter rather than by
# blindly copying the database.
LEGACY_COLUMN_ALIASES: dict[str, dict[str, str]] = {
    "users": {
        "expire_date": "expire",
        "data_limit_reset": "data_limit_reset_strategy",
    },
    "nodes": {
        "certificate": "server_ca",
    },
}


def normalize_core_type(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "xray"
    value = str(value).strip().lower()
    aliases = {
        "wireguard": "wg",
        "wire_guard": "wg",
        "amnezia-wg": "amneziawg",
        "amnezia_wg": "amneziawg",
    }
    return aliases.get(value, value)


def is_supported_core_type(value: str | None) -> bool:
    return normalize_core_type(value) in {"xray", "wg", "amneziawg", "mtproto", "singbox"}
