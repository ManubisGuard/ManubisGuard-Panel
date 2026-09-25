from fastapi import status

from tests.api import client
from tests.api.helpers import auth_headers


def test_general_settings_custom_variables_round_trip(access_token):
    settings_response = client.get("/api/settings", headers=auth_headers(access_token))
    assert settings_response.status_code == status.HTTP_200_OK
    original_subscription = settings_response.json()["subscription"]

    custom_variables = [{"key": "CUSTOM_GENERAL_HOST", "value": "{USERNAME}.example.com"}]

    try:
        update_response = client.put(
            "/api/settings",
            headers=auth_headers(access_token),
            json={
                "general": {
                    "default_method": settings_response.json()["general"]["default_method"],
                    "custom_variables": custom_variables,
                }
            },
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["general"]["custom_variables"] == custom_variables
        assert update_response.json()["subscription"]["custom_variables"] == custom_variables

        general_response = client.get("/api/settings/general", headers=auth_headers(access_token))
        assert general_response.status_code == status.HTTP_200_OK
        assert general_response.json()["custom_variables"] == custom_variables
    finally:
        restore_response = client.put(
            "/api/settings",
            headers=auth_headers(access_token),
            json={"subscription": original_subscription},
        )
        assert restore_response.status_code == status.HTTP_200_OK


def test_domains_partial_update_preserves_other_general_settings(access_token):
    settings_response = client.get("/api/settings", headers=auth_headers(access_token))
    assert settings_response.status_code == status.HTTP_200_OK
    original = settings_response.json()["general"]
    original_subscription = settings_response.json()["subscription"]

    domain = {
        "id": "domain-preservation-test",
        "domain": "edge.example.com",
        "node_id": None,
        "certificate_method": "letsencrypt",
        "address_mode": "additional",
        "protocols": ["xray"],
        "email": None,
        "auto_renew": True,
        "status": "pending",
        "certificate_expires_at": None,
        "certificate_issued_at": None,
        "certificate_renewed_at": None,
        "certificate_error": None,
        "renewal_attempts": 0,
        "next_renewal_at": None,
        "deployment_status": "not_deployed",
        "certificate_deployed_at": None,
        "deployment_error": None,
        "last_checked_at": None,
    }

    try:
        update_response = client.put(
            "/api/settings",
            headers=auth_headers(access_token),
            json={
                "general": {
                    "domains": [domain],
                    "primary_domain": domain,
                    "server_addresses": [],
                }
            },
        )
        assert update_response.status_code == status.HTTP_200_OK
        updated = update_response.json()
        updated_general = updated["general"]

        assert updated_general["domains"] == [domain]
        assert updated_general["primary_domain"] == domain
        assert updated_general["server_addresses"] == []
        assert updated_general["default_method"] == original["default_method"]
        assert updated_general["reality_sni_pool"] == original["reality_sni_pool"]
        assert updated["subscription"]["custom_variables"] == original_subscription["custom_variables"]
        assert updated_general["custom_variables"] == updated["subscription"]["custom_variables"]
    finally:
        restore_response = client.put(
            "/api/settings",
            headers=auth_headers(access_token),
            json={"general": original},
        )
        assert restore_response.status_code == status.HTTP_200_OK


def test_domain_intelligence_api_returns_inspection(monkeypatch, access_token):
    from app.core.domain_intelligence import DomainIntelligence
    from app.models.domain_intelligence import DomainDNSResult, DomainHTTPProbe, DomainIntelligenceResult

    async def fake_inspect(self, domain):
        assert domain == "edge.example.com"
        return DomainIntelligenceResult.now(
            domain,
            DomainDNSResult(a=["203.0.113.10"]),
            DomainHTTPProbe(url="http://edge.example.com", error="ClientConnectorError"),
            DomainHTTPProbe(
                url="https://edge.example.com",
                reachable=True,
                status_code=200,
                final_url="https://edge.example.com/",
            ),
        )

    monkeypatch.setattr(DomainIntelligence, "inspect", fake_inspect)

    response = client.post(
        "/api/settings/domains/intelligence",
        headers=auth_headers(access_token),
        json={"domain": "  Edge.Example.COM  "},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["domain"] == "edge.example.com"
    assert payload["status"] == "healthy"
    assert payload["dns"]["a"] == ["203.0.113.10"]
    assert payload["https"]["status_code"] == 200


def test_domain_intelligence_api_rejects_invalid_domain(access_token):
    response = client.post(
        "/api/settings/domains/intelligence",
        headers=auth_headers(access_token),
        json={"domain": "https://edge.example.com"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_domain_certificate_api_returns_certificate(monkeypatch, access_token):
    from app.core.certificate_intelligence import DomainCertificateInspector
    from app.models.domain_intelligence import DomainCertificateResult

    async def fake_inspect(self, domain):
        assert domain == "edge.example.com"
        return DomainCertificateResult(
            domain=domain,
            checked_at="2026-09-23T00:00:00Z",
            reachable=True,
            valid=True,
            expires_at="2099-12-31T23:59:59Z",
            days_remaining=26784,
            subject="edge.example.com",
            issuer="Test CA",
            serial_number="01",
            tls_version="TLSv1.3",
            san=["edge.example.com"],
            status="valid",
        )

    monkeypatch.setattr(DomainCertificateInspector, "inspect", fake_inspect)

    response = client.post(
        "/api/settings/domains/certificate",
        headers=auth_headers(access_token),
        json={"domain": "  Edge.Example.COM  "},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["domain"] == "edge.example.com"
    assert payload["status"] == "valid"
    assert payload["tls_version"] == "TLSv1.3"


def test_domain_certificate_api_rejects_invalid_domain(access_token):
    response = client.post(
        "/api/settings/domains/certificate",
        headers=auth_headers(access_token),
        json={"domain": "edge.example.com:443"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
