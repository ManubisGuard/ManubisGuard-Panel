import pytest

from app.core.domain_intelligence import DomainIntelligence
from app.models.domain_intelligence import DomainDNSResult, DomainHTTPProbe, DomainIntelligenceResult


def test_domain_intelligence_result_classifies_https_and_redirects():
    dns = DomainDNSResult(
        a=["203.0.113.10"],
        aaaa=["2001:db8::10"],
        cname="edge.example.net",
        nameservers=["ns1.example.net"],
    )
    http = DomainHTTPProbe(
        url="http://edge.example.com",
        reachable=True,
        status_code=301,
        final_url="https://edge.example.com/",
        redirect_chain=["http://edge.example.com"],
    )
    https = DomainHTTPProbe(
        url="https://edge.example.com",
        reachable=True,
        status_code=200,
        final_url="https://edge.example.com/",
    )

    result = DomainIntelligenceResult.now("edge.example.com", dns, http, https)

    assert result.status == "redirected"
    assert result.tls_valid is True
    assert result.service_hints == ["http:80", "https:443"]
    assert result.dns.cname == "edge.example.net"


@pytest.mark.asyncio
async def test_domain_intelligence_normalizes_domain_and_uses_deterministic_probes(monkeypatch):
    inspector = DomainIntelligence(timeout=1)

    async def fake_resolve(self, session, domain):
        assert domain == "edge.example.com"
        return DomainDNSResult(a=["203.0.113.10"])

    async def fake_probe(self, session, url):
        if url.startswith("https://"):
            return DomainHTTPProbe(
                url=url,
                reachable=True,
                status_code=200,
                final_url=url,
            )
        return DomainHTTPProbe(url=url, error="ClientConnectorError")

    monkeypatch.setattr(DomainIntelligence, "_resolve_dns", fake_resolve)
    monkeypatch.setattr(DomainIntelligence, "_probe", fake_probe)

    result = await inspector.inspect("  Edge.Example.COM  ")

    assert result.domain == "edge.example.com"
    assert result.dns.a == ["203.0.113.10"]
    assert result.http.reachable is False
    assert result.https.reachable is True
    assert result.status == "healthy"


@pytest.mark.asyncio
async def test_domain_intelligence_rejects_invalid_domains():
    inspector = DomainIntelligence(timeout=1)

    with pytest.raises(ValueError):
        await inspector.inspect("https://edge.example.com")


def test_is_https_url():
    assert DomainIntelligence.is_https_url("https://example.com") is True
    assert DomainIntelligence.is_https_url("http://example.com") is False
