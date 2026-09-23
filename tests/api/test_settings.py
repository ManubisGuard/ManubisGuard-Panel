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
        updated_general = update_response.json()["general"]

        assert updated_general["domains"] == [domain]
        assert updated_general["primary_domain"] == domain
        assert updated_general["server_addresses"] == []
        assert updated_general["default_method"] == original["default_method"]
        assert updated_general["reality_sni_pool"] == original["reality_sni_pool"]
        assert updated_general["custom_variables"] == original["custom_variables"]
    finally:
        restore_response = client.put(
            "/api/settings",
            headers=auth_headers(access_token),
            json={"general": original},
        )
        assert restore_response.status_code == status.HTTP_200_OK
