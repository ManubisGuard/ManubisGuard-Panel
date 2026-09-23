"""Contract coverage for the public PasarGuard API surface used by existing clients.

ManubisGuard intentionally keeps the PasarGuard-compatible HTTP contract. These tests
guard the paths that external bots/SDKs use so internal refactors do not silently
break existing integrations.
"""

from fastapi import APIRouter

from app.routers import api_router


def _route_contract(router: APIRouter) -> set[tuple[str, str]]:
    contracts: set[tuple[str, str]] = set()
    for route in router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            contracts.add((method.upper(), path))
    return contracts


REQUIRED_ROUTES = {
    ("POST", "/api/user"),
    ("GET", "/api/user/{user_id}/subscription/{client_type}"),
    ("GET", "/api/user/{username}"),
    ("GET", "/api/users"),
    ("GET", "/api/user/{user_id}/hwids"),
    ("POST", "/api/user/{user_id}/hwids/reset"),
    ("GET", "/api/admins"),
    ("POST", "/api/admin/token"),
    ("GET", "/api/admin-roles"),
    ("GET", "/api/api_keys"),
    ("GET", "/api/api_key/{key_id}"),
    ("GET", "/api/client_template/{template_id}"),
    ("GET", "/api/client_templates"),
    ("GET", "/api/core/{core_id}"),
    ("GET", "/api/cores"),
    ("GET", "/api/groups"),
    ("GET", "/api/group/{group_id}"),
    ("GET", "/api/host/{host_id}"),
    ("GET", "/api/hosts"),
    ("GET", "/api/nodes"),
    ("GET", "/api/node/{node_id}"),
    ("POST", "/api/nodes/bulk/update"),
    ("GET", "/api/settings"),
    ("GET", "/api/system"),
    ("GET", "/api/system/resources"),
    ("GET", "/api/system/users"),
    ("GET", "/api/inbounds"),
    ("GET", "/api/inbounds/details"),
    ("GET", "/api/user_template/{template_id}"),
    ("GET", "/api/user_templates"),
}


def test_pasarguard_public_contract_is_present():
    actual = _route_contract(api_router)
    missing = sorted(REQUIRED_ROUTES - actual)
    assert not missing, "PasarGuard compatibility routes missing: " + ", ".join(
        f"{method} {path}" for method, path in missing
    )
