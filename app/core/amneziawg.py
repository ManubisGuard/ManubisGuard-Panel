from __future__ import annotations

from copy import deepcopy

from app.core.wireguard import WireGuardConfig

# AmneziaWG 2.x parameters. These are serialized into the same core config
# payload as WireGuard, but use a dedicated core type so the two protocols
# can coexist without changing existing WireGuard behavior.
AWG_OBFUSCATION_FIELDS = (
    "jc",
    "jmin",
    "jmax",
    "s1",
    "s2",
    "s3",
    "s4",
    "h1",
    "h2",
    "h3",
    "h4",
    "i1",
    "i2",
    "i3",
    "i4",
    "i5",
)


class AmneziaWGConfig(WireGuardConfig):
    """AmneziaWG core configuration.

    The transport remains WireGuard-compatible at the key/address/peer level,
    while AWG-specific obfuscation parameters are validated and preserved in
    the core config. Runtime node support is intentionally added separately so
    existing WG nodes are not changed implicitly.
    """

    def _validate(self):
        super()._validate()
        self["amneziawg"] = True

        for field in AWG_OBFUSCATION_FIELDS:
            if field not in self:
                continue
            value = self[field]
            if field.startswith("h") or field.startswith("i"):
                if not isinstance(value, str):
                    raise TypeError(f"{field} must be a string")
                value = value.strip()
                if not value:
                    self.pop(field, None)
                else:
                    self[field] = value
                continue

            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
            self[field] = value

        # Keep validation semantics aligned with the AWG 2.x runtime implementation.
        # The node validates the same values with awgctrl-go before applying them.

    def _resolve_inbounds(self):
        super()._resolve_inbounds()
        for metadata in self._inbounds_by_tag.values():
            metadata["protocol"] = "amneziawg"
            metadata["amneziawg"] = {
                field: self[field] for field in AWG_OBFUSCATION_FIELDS if field in self
            }

    @property
    def type(self) -> str:
        return "amneziawg"

    def to_json(self) -> dict:
        data = super().to_json()
        data["type"] = self.type
        return data

    @classmethod
    def from_json(cls, data: dict) -> AmneziaWGConfig:
        instance = cls(config=data.get("config", {}), skip_validation=True)
        if "inbounds" in data:
            instance._inbounds = data["inbounds"]
        if "inbounds_by_tag" in data:
            instance._inbounds_by_tag = data["inbounds_by_tag"]
        return instance

    def copy(self):
        return deepcopy(self)
