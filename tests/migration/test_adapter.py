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


def test_adapter_defines_pre_migration_certificate_snapshot():
    from app.migration.adapters.pasarguard import LEGACY_SNAPSHOT_NODE_CERTIFICATE

    assert LEGACY_SNAPSHOT_NODE_CERTIFICATE == "_manubisguard_legacy_node_certificate"
