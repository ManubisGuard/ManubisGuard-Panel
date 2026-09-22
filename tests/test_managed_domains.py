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
