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


def test_certificate_inspector_classifies_valid_certificate(monkeypatch):
    from app.core.certificate_intelligence import DomainCertificateInspector

    inspector = DomainCertificateInspector(expiring_days=30)

    class FakeTLS:
        def getpeercert(self):
            return {
                "notAfter": "Dec 31 23:59:59 2099 GMT",
                "subjectAltName": (("DNS", "edge.example.com"),),
                "subject": ((("commonName", "edge.example.com"),),),
                "issuer": ((("commonName", "Test CA"),),),
                "serialNumber": "01",
            }

        def version(self):
            return "TLSv1.3"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeContext:
        def wrap_socket(self, raw_socket, server_hostname):
            assert server_hostname == "edge.example.com"
            return FakeTLS()

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("ssl.create_default_context", lambda: FakeContext())
    monkeypatch.setattr("socket.create_connection", lambda address, timeout: FakeSocket())

    result = __import__("asyncio").run(inspector.inspect("Edge.Example.COM"))

    assert result.domain == "edge.example.com"
    assert result.reachable is True
    assert result.valid is True
    assert result.status == "valid"
    assert result.tls_version == "TLSv1.3"
    assert result.san == ["edge.example.com"]


@pytest.mark.asyncio
async def test_certificate_inspector_handles_unreachable_domain(monkeypatch):
    from app.core.certificate_intelligence import DomainCertificateInspector

    def fail(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr("socket.create_connection", fail)

    result = await DomainCertificateInspector(timeout=1).inspect("edge.example.com")

    assert result.reachable is False
    assert result.status == "unreachable"
    assert result.error == "TimeoutError"
