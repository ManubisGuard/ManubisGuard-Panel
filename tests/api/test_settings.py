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
        "serve_tls": True,
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


def test_managed_certificate_issue_auto_saves_domain_before_issuance(access_token, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import app.routers.settings as settings_router
    from app.models.settings import ManagedDomain

    issued = ManagedDomain(
        id="auto-save-1",
        domain="edge.example.com",
        node_id=None,
        status="active",
        certificate_expires_at="2099-12-31T23:59:59Z",
    )
    service = SimpleNamespace(
        renew_if_due=AsyncMock(return_value=issued), list_domains=AsyncMock(return_value=[issued])
    )
    monkeypatch.setattr(settings_router, "ManagedCertificateService", lambda: service)

    settings_response = client.get("/api/settings", headers=auth_headers(access_token))
    assert settings_response.status_code == 200
    original_general = settings_response.json()["general"]

    try:
        response = client.post(
            "/api/settings/domains/certificate/issue",
            headers=auth_headers(access_token),
            json={
                "domain_id": "auto-save-1",
                "force": True,
                "primary": False,
                "domain": {
                    "id": "auto-save-1",
                    "domain": "edge.example.com",
                    "node_id": None,
                    "certificate_method": "letsencrypt",
                    "address_mode": "additional",
                    "protocols": ["Xray"],
                    "email": None,
                    "auto_renew": True,
                    "serve_tls": True,
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
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["domain"]["id"] == "auto-save-1"
        saved = client.get("/api/settings/general", headers=auth_headers(access_token)).json()
        assert any(item["id"] == "auto-save-1" for item in saved["domains"])
        service.renew_if_due.assert_awaited_once()
    finally:
        restore = client.put("/api/settings", headers=auth_headers(access_token), json={"general": original_general})
        assert restore.status_code == 200


def test_cloudflare_token_status_and_storage_are_write_only(access_token):
    settings_response = client.get("/api/settings", headers=auth_headers(access_token))
    assert settings_response.status_code == 200
    original_general = settings_response.json()["general"]

    try:
        save = client.put(
            "/api/settings/domains/certificate/cloudflare",
            headers=auth_headers(access_token),
            json={"api_token": "test-cloudflare-token"},
        )
        assert save.status_code == 200
        assert save.json() == {"configured": True}

        status_response = client.get("/api/settings/domains/certificate/cloudflare", headers=auth_headers(access_token))
        assert status_response.status_code == 200
        assert status_response.json() == {"configured": True}

        general_response = client.get("/api/settings/general", headers=auth_headers(access_token))
        assert general_response.status_code == 200
        assert "test-cloudflare-token" not in general_response.text
    finally:
        restore = client.put("/api/settings", headers=auth_headers(access_token), json={"general": original_general})
        assert restore.status_code == 200


def test_managed_certificate_deploy_endpoint_reapplies_node_config(access_token, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import app.routers.settings as settings_router
    from app.models.settings import ManagedDomain

    target = ManagedDomain(id="deploy-1", domain="edge.example.com", node_id=7, status="active")
    deployed = target.model_copy(
        update={"deployment_status": "deployed", "certificate_deployed_at": "2030-01-01T00:00:00+00:00"}
    )
    service = SimpleNamespace(
        list_domains=AsyncMock(side_effect=[[target], [deployed]]),
        store=SimpleNamespace(exists=lambda _: True),
    )
    connect = AsyncMock()
    monkeypatch.setattr(settings_router, "ManagedCertificateService", lambda: service)
    monkeypatch.setattr(settings_router.node_operator, "connect_single_node", connect)

    response = client.post(
        "/api/settings/domains/certificate/deploy",
        headers=auth_headers(access_token),
        json={"domain_id": "deploy-1"},
    )

    assert response.status_code == 200
    assert response.json()["domain"]["deployment_status"] == "deployed"
    connect.assert_awaited_once()
    assert connect.await_args.args[1] == 7
    assert connect.await_args.kwargs["force_start"] is True
