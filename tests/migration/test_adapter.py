from app.migration.adapters.pasarguard import PasarGuardAdapter


def test_adapter_normalizes_legacy_core_type_aliases():
    adapter = PasarGuardAdapter()
    assert adapter.normalize_core_type("wireguard") == "wg"
    assert adapter.normalize_core_type("wire_guard") == "wg"
    assert adapter.normalize_core_type("amnezia-wg") == "amneziawg"
    assert adapter.normalize_core_type("amnezia_wg") == "amneziawg"


def test_adapter_does_not_invent_amneziawg():
    adapter = PasarGuardAdapter()
    assert adapter.normalize_core_type("xray") == "xray"
    assert adapter.normalize_core_type("wg") == "wg"
