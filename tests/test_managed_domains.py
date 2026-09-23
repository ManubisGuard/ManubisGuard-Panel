import pytest

from app.models.settings import General, ManagedDomain, ManagedServerAddress


def test_general_managed_domains_default_empty():
    general = General()
    assert general.domains == []
    assert general.primary_domain is None
    assert general.server_addresses == []


def test_managed_domain_normalizes_hostname():
    domain = ManagedDomain(id="d1", domain="  Edge.Example.COM  ")
    assert domain.domain == "edge.example.com"


@pytest.mark.parametrize("address", ["203.0.113.10", "2001:db8::10", "edge.example.com"])
def test_managed_server_address_accepts_ip_or_hostname(address):
    item = ManagedServerAddress(id="a1", address=address)
    assert item.address == address.lower()


@pytest.mark.parametrize("address", ["https://edge.example.com", "edge.example.com:443", "edge.example.com/path"])
def test_managed_server_address_rejects_url_forms(address):
    with pytest.raises(ValueError):
        ManagedServerAddress(id="a1", address=address)


@pytest.mark.parametrize(
    "domain",
    [
        "https://edge.example.com",
        "edge.example.com:443",
        "edge.example.com/path",
        "edge.example.com path",
        "localhost",
    ],
)
def test_managed_domain_rejects_url_port_path_whitespace_and_localhost(domain):
    with pytest.raises(ValueError):
        ManagedDomain(id="d1", domain=domain)


def test_managed_domain_normalizes_valid_hostname():
    item = ManagedDomain(id="d1", domain="  Edge.Example.COM  ")
    assert item.domain == "edge.example.com"


def test_general_preserves_managed_domain_configuration():
    domain = ManagedDomain(
        id="d1",
        domain="Edge.Example.COM",
        node_id=7,
        certificate_method="cloudflare",
        address_mode="both",
        protocols=["Xray", "AmneziaWG"],
        email="admin@example.com",
        auto_renew=False,
        status="active",
        certificate_expires_at="2030-01-01T00:00:00Z",
        last_checked_at="2029-12-01T00:00:00Z",
    )
    address = ManagedServerAddress(id="a1", node_id=7, address="203.0.113.10", enabled=False)
    general = General(primary_domain=domain, domains=[domain], server_addresses=[address])

    assert general.primary_domain == domain
    assert general.domains == [domain]
    assert general.server_addresses == [address]


def test_managed_domain_accepts_acme_wildcard_hostname():
    item = ManagedDomain(id="wildcard", domain="*.Edge.Example.COM")
    assert item.domain == "*.edge.example.com"


@pytest.mark.parametrize("domain", ["*.*.example.com", "foo.*.example.com", "*"])
def test_managed_domain_rejects_invalid_wildcard_hostname(domain):
    with pytest.raises(ValueError):
        ManagedDomain(id="wildcard-invalid", domain=domain)
