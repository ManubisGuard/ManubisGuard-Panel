from fastapi import APIRouter

from . import (
    acme,
    admin,
    admin_role,
    admin_backup,
    api_key,
    client_template,
    core,
    group,
    home,
    host,
    hwid,
    node,
    settings,
    setup,
    subscription,
    system,
    user,
    user_template,
)

api_router = APIRouter()

routers = [
    acme.router,
    home.router,
    admin.router,
    admin_backup.router,
    api_key.router,
    admin_role.router,
    setup.router,
    system.router,
    settings.router,
    group.router,
    core.router,
    client_template.router,
    host.router,
    node.router,
    user.router,
    subscription.router,
    user_template.router,
    hwid.router,
]

for router in routers:
    api_router.include_router(router)

__all__ = ["api_router"]
