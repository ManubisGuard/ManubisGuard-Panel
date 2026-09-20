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
            if field.startswith(("h", "i")):
                if not isinstance(value, str):
                    raise TypeError(f"{field} must be a string")
                value = value.strip()
                if not value:
                    self.pop(field, None)
                else:
                    self[field] = value
                continue

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")

            # Do not impose an application-defined AWG numeric range here.
            # The node/kernel implementation remains the final authority for
            # protocol-level representability and safety. Keep only the type
            # contract at the panel boundary so valid future AWG values are not
            # blocked by stale UI-side limits.
            self[field] = value

        jmin = self.get("jmin")
        jmax = self.get("jmax")
        if jmin is not None and jmax is not None and jmin > jmax:
            raise ValueError("jmin must be less than or equal to jmax")

        # The node performs the final protocol/kernel validation before applying
        # the configuration. The panel intentionally avoids duplicating a fixed
        # AWG range so newer kernel/runtime capabilities are not blocked here.

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
