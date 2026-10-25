from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.db.models import HostAdminName, ProxyHost
from app.subscription.config_cache import clear_sub_config_cache

from app.db import AsyncSession, get_db
from app.models.admin import AdminDetails
from app.models.host import BaseHost, BulkHostsActionResponse, BulkHostSelection, CreateHost, RemoveHostsResponse
from app.operation import OperatorType
from app.operation.host import HostOperation
from app.utils import responses

from .authentication import require_permission
from .dependencies import get_host_list_query

host_operator = HostOperation(operator_type=OperatorType.API)


class PersonalHostName(BaseModel):
    remark: str = Field(min_length=1, max_length=256)


class PersonalHostNameEntry(BaseModel):
    host_id: int
    host_name: str
    personal_name: str | None = None

router = APIRouter(tags=["Host"], prefix="/api/host", responses={401: responses._401, 403: responses._403})


@router.get("/personal-names", response_model=list[PersonalHostNameEntry])
async def get_personal_host_names(
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "personal_name")),
):
    """Return only host IDs and this admin's personal labels, never host configuration."""
    if not admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin identity is required")
    allowed_group_ids = admin.role.access.allowed_group_ids if admin.role and admin.role.access else None
    if allowed_group_ids is not None:
        from app.db.models import Group, ProxyInbound, inbounds_groups_association
        if not allowed_group_ids:
            return []
        result = await db.execute(
            select(ProxyHost.id, ProxyHost.remark, HostAdminName.remark)
            .join(ProxyInbound, ProxyHost.inbound_tag == ProxyInbound.tag)
            .join(inbounds_groups_association, inbounds_groups_association.c.inbound_id == ProxyInbound.id)
            .join(Group, Group.id == inbounds_groups_association.c.group_id)
            .outerjoin(HostAdminName, (HostAdminName.host_id == ProxyHost.id) & (HostAdminName.admin_id == admin.id))
            .where(Group.id.in_(allowed_group_ids), Group.is_disabled.is_(False))
            .distinct().order_by(ProxyHost.id)
        )
    else:
        result = await db.execute(
            select(ProxyHost.id, ProxyHost.remark, HostAdminName.remark)
            .outerjoin(HostAdminName, (HostAdminName.host_id == ProxyHost.id) & (HostAdminName.admin_id == admin.id))
            .order_by(ProxyHost.id)
        )
    return [PersonalHostNameEntry(host_id=host_id, host_name=host_name, personal_name=personal_name)
            for host_id, host_name, personal_name in result.all()]


@router.get("/{host_id}", response_model=BaseHost)
async def get_host(
    host_id: int, db: AsyncSession = Depends(get_db), _: AdminDetails = Depends(require_permission("hosts", "read"))
):
    """
    get host by **id**
    """
    return await host_operator.get_validated_host(db=db, host_id=host_id)


@router.get("s", response_model=list[BaseHost])
async def get_hosts(
    query=Depends(get_host_list_query),
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "read")),
):
    """
    Get proxy hosts.
    """
    hosts = await host_operator.get_hosts(db=db, query=query)
    if admin.id and hosts:
        result = await db.execute(select(HostAdminName).where(
            HostAdminName.admin_id == admin.id,
            HostAdminName.host_id.in_([host.id for host in hosts if host.id is not None]),
        ))
        personal_names = {row.host_id: row.remark for row in result.scalars().all()}
        for host in hosts:
            if host.id in personal_names:
                # Keep the canonical remark untouched: host edit/toggle forms submit it.
                # Expose the personal label separately to avoid overwriting the shared host.
                host.personal_remark = personal_names[host.id]
    return hosts


@router.put("/{host_id}/personal-name", response_model=PersonalHostNameEntry)
async def set_personal_host_name(
    host_id: int,
    payload: PersonalHostName,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "personal_name")),
):
    """Set a display name visible only to this admin and their own users."""
    host = await host_operator.get_validated_host(db=db, host_id=host_id)
    if admin.role and admin.role.access and admin.role.access.allowed_group_ids is not None:
        from app.db.models import Group, ProxyInbound, inbounds_groups_association
        allowed_group_ids = admin.role.access.allowed_group_ids
        if not allowed_group_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        permitted = await db.execute(
            select(ProxyHost.id)
            .join(ProxyInbound, ProxyHost.inbound_tag == ProxyInbound.tag)
            .join(inbounds_groups_association, inbounds_groups_association.c.inbound_id == ProxyInbound.id)
            .join(Group, Group.id == inbounds_groups_association.c.group_id)
            .where(ProxyHost.id == host_id, Group.id.in_(allowed_group_ids), Group.is_disabled.is_(False))
            .limit(1)
        )
        if permitted.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
    if not admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin identity is required")
    result = await db.execute(select(HostAdminName).where(
        HostAdminName.admin_id == admin.id,
        HostAdminName.host_id == host_id,
    ))
    personal_name = result.scalar_one_or_none()
    name = payload.remark.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
    if personal_name is None:
        personal_name = HostAdminName(admin_id=admin.id, host_id=host_id, remark=name)
        db.add(personal_name)
    else:
        personal_name.remark = name
    await db.commit()
    clear_sub_config_cache()
    return PersonalHostNameEntry(host_id=host_id, host_name=host.remark, personal_name=name)


@router.post("/", response_model=BaseHost, status_code=status.HTTP_201_CREATED)
async def create_host(
    new_host: CreateHost,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "create")),
):
    """
    create a new host

    **inbound_tag** must be available in one of the configured cores
    """
    return await host_operator.create_host(db, new_host=new_host, admin=admin)


@router.put("/{host_id}", response_model=BaseHost, responses={404: responses._404})
async def modify_host(
    host_id: int,
    modified_host: CreateHost,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "update")),
):
    """
    modify host by **id**

    **inbound_tag** must be available in one of the configured cores
    """
    return await host_operator.modify_host(db, host_id=host_id, modified_host=modified_host, admin=admin)


@router.delete(
    "/{host_id}",
    responses={404: responses._404},
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_host(
    host_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "update")),
):
    """
    remove host by **id**
    """
    await host_operator.remove_host(db, host_id=host_id, admin=admin)
    return {}


@router.put("s", response_model=list[BaseHost])
async def modify_hosts(
    modified_hosts: list[CreateHost],
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "update")),
):
    """
    Modify proxy hosts and update the configuration.
    """
    return await host_operator.modify_hosts(db=db, modified_hosts=modified_hosts, admin=admin)


@router.post(
    "s/bulk/delete",
    response_model=RemoveHostsResponse,
    responses={400: responses._400, 403: responses._403, 404: responses._404},
)
async def bulk_delete_hosts(
    bulk_hosts: BulkHostSelection,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "update")),
):
    """Delete selected hosts by ID."""
    return await host_operator.bulk_remove_hosts(db, bulk_hosts, admin)


@router.post(
    "s/bulk/disable",
    response_model=BulkHostsActionResponse,
    responses={400: responses._400, 403: responses._403, 404: responses._404},
)
async def bulk_disable_hosts(
    bulk_hosts: BulkHostSelection,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "update")),
):
    """Disable selected hosts by ID."""
    return await host_operator.bulk_set_hosts_disabled(db, bulk_hosts, admin, is_disabled=True)


@router.post(
    "s/bulk/enable",
    response_model=BulkHostsActionResponse,
    responses={400: responses._400, 403: responses._403, 404: responses._404},
)
async def bulk_enable_hosts(
    bulk_hosts: BulkHostSelection,
    db: AsyncSession = Depends(get_db),
    admin: AdminDetails = Depends(require_permission("hosts", "update")),
):
    """Enable selected hosts by ID."""
    return await host_operator.bulk_set_hosts_disabled(db, bulk_hosts, admin, is_disabled=False)
