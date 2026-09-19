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

            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
            self[field] = value

        jc = self.get("jc")
        jmin = self.get("jmin")
        jmax = self.get("jmax")
        if jc is not None and jc > 10:
            raise ValueError("jc must be between 0 and 10")
        if jmin is not None and (jmin < 64 or jmin > 1024):
            raise ValueError("jmin must be between 64 and 1024")
        if jmax is not None and (jmax < 64 or jmax > 1024):
            raise ValueError("jmax must be between 64 and 1024")
        if jmin is not None and jmax is not None and jmax < jmin:
            raise ValueError("jmax must be greater than or equal to jmin")

        for field in ("s1", "s2", "s3", "s4"):
            value = self.get(field)
            if value is not None and (value < 0 or value > (32 if field == "s4" else 64)):
                raise ValueError(f"{field} is outside the supported AmneziaWG kernel range")

        headers = [self.get(f"h{i}") for i in range(1, 5)]
        headers = [h for h in headers if h]
        if len(headers) != len(set(headers)):
            raise ValueError("h1, h2, h3 and h4 must be unique")

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
