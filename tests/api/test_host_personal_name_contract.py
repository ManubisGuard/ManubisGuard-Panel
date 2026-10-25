"""Regression tests for the least-privilege personal host-name API contract."""

from app.routers.host import PersonalHostNameEntry, router


def test_personal_host_name_response_exposes_only_id_and_own_label():
    assert set(PersonalHostNameEntry.model_fields) == {"host_id", "host_name", "personal_name"}


def test_personal_host_name_endpoints_use_minimal_response_models():
    routes = {
        (route.path, method): route
        for route in router.routes
        for method in getattr(route, "methods", set())
    }

    list_route = routes[("/api/host/personal-names", "GET")]
    update_route = routes[("/api/host/{host_id}/personal-name", "PUT")]

    assert list_route.response_model == list[PersonalHostNameEntry]
    assert update_route.response_model is PersonalHostNameEntry
