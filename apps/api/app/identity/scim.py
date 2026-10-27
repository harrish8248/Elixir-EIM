"""SCIM 2.0 (RFC 7643 / RFC 7644) Users and Groups Implementation with Per-Tenant Bearer Auth."""

import hashlib
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.identity.models import Group, GroupMember, ScimBearerToken, User
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.context import set_current_tenant_id
from apps.api.app.tenancy.database import get_db_session

scim_router = APIRouter(prefix="/api/v1/scim/v2", tags=["SCIM 2.0"])

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def hash_token(raw_token: str) -> str:
    """Hash raw bearer token with SHA-256 for secure storage and comparison."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


async def verify_scim_bearer_token(
    authorization: str | None = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db_session),
) -> UUID:
    """
    Authenticate SCIM 2.0 requests via per-tenant Bearer token.
    Enforces tenant context isolation for downstream database queries.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization Bearer header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = authorization.split("Bearer ", 1)[1].strip()
    token_digest = hash_token(raw_token)

    # Query active token from scim_bearer_tokens
    stmt = select(ScimBearerToken).where(
        ScimBearerToken.token_hash == token_digest,
        ScimBearerToken.is_active == True,
    )
    res = await db.execute(stmt)
    token_record = res.scalar_one_or_none()

    if not token_record:
        logger.warning("Rejected invalid or inactive SCIM bearer token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired SCIM bearer token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    # Bind request execution context to token's isolated tenant
    set_current_tenant_id(token_record.tenant_id)
    from sqlalchemy import text

    # Set connection-level session config so it survives commits within the request
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
        {"tenant_id": str(token_record.tenant_id)},
    )
    return token_record.tenant_id


# ==============================================================================
# SCIM 2.0 Pydantic Schemas
# ==============================================================================


class ScimName(BaseModel):
    givenName: str | None = None
    familyName: str | None = None
    formatted: str | None = None


class ScimEmail(BaseModel):
    value: str
    primary: bool = True
    type: str = "work"


class ScimUserCreate(BaseModel):
    schemas: list[str] = [SCIM_USER_SCHEMA]
    userName: str
    externalId: str | None = None
    name: ScimName | None = None
    emails: list[ScimEmail] = Field(default_factory=list)
    active: bool = True
    roles: list[str] = Field(default_factory=list)
    department: str | None = None


class ScimMemberItem(BaseModel):
    value: str
    display: str | None = None


class ScimGroupCreate(BaseModel):
    schemas: list[str] = [SCIM_GROUP_SCHEMA]
    displayName: str
    members: list[ScimMemberItem] = Field(default_factory=list)


def user_to_scim_dict(user: User, req: Request) -> dict[str, Any]:
    """Serialize a database User entity to RFC 7643 SCIM 2.0 User resource."""
    base_url = str(req.base_url).rstrip("/")
    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": str(user.id),
        "externalId": user.external_id,
        "userName": user.username,
        "name": {
            "formatted": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "givenName": user.first_name,
            "familyName": user.last_name,
        },
        "emails": [{"value": user.email, "primary": True, "type": "work"}],
        "active": user.is_active,
        "roles": [{"value": r} for r in user.roles],
        "department": user.department,
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat(),
            "lastModified": user.updated_at.isoformat(),
            "location": f"{base_url}/api/v1/scim/v2/Users/{user.id}",
        },
    }


def group_to_scim_dict(
    group: Group, req: Request, members: list[User] | None = None
) -> dict[str, Any]:
    """Serialize a database Group entity to RFC 7643 SCIM 2.0 Group resource."""
    base_url = str(req.base_url).rstrip("/")
    member_list = []
    if members:
        for m in members:
            member_list.append(
                {
                    "value": str(m.id),
                    "display": f"{m.first_name or ''} {m.last_name or ''}".strip() or m.username,
                    "$ref": f"{base_url}/api/v1/scim/v2/Users/{m.id}",
                }
            )

    return {
        "schemas": [SCIM_GROUP_SCHEMA],
        "id": str(group.id),
        "displayName": group.name,
        "members": member_list,
        "meta": {
            "resourceType": "Group",
            "created": group.created_at.isoformat(),
            "lastModified": group.updated_at.isoformat(),
            "location": f"{base_url}/api/v1/scim/v2/Groups/{group.id}",
        },
    }


# ==============================================================================
# SCIM 2.0 Users Endpoints
# ==============================================================================


@scim_router.get("/Users", response_model=dict[str, Any])
async def list_scim_users(
    request: Request,
    filter: str | None = Query(None),
    startIndex: int = Query(1, ge=1),
    count: int = Query(50, ge=1, le=100),
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List users for the authenticated tenant with SCIM 2.0 pagination and RFC 7644 filtering."""
    filter_clause = None
    if filter:
        if "userName eq " in filter:
            val = filter.split("userName eq ", 1)[1].strip().strip('"').strip("'")
            filter_clause = (User.username == val)
        elif "email eq " in filter:
            val = filter.split("email eq ", 1)[1].strip().strip('"').strip("'")
            filter_clause = (User.email == val)
        elif "externalId eq " in filter:
            val = filter.split("externalId eq ", 1)[1].strip().strip('"').strip("'")
            filter_clause = (User.external_id == val)

    # Count total results for tenant
    count_stmt = select(func.count(User.id)).where(User.tenant_id == tenant_id)
    if filter_clause is not None:
        count_stmt = count_stmt.where(filter_clause)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch paginated slice
    offset = startIndex - 1
    stmt = select(User).where(User.tenant_id == tenant_id)
    if filter_clause is not None:
        stmt = stmt.where(filter_clause)
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(count)
    users = (await db.execute(stmt)).scalars().all()

    resources = [user_to_scim_dict(u, request) for u in users]
    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": total,
        "startIndex": startIndex,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


@scim_router.post("/Users", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
async def create_scim_user(
    payload: ScimUserCreate,
    request: Request,
    response: Response,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Provision a new user via SCIM 2.0."""
    email_val = payload.emails[0].value if payload.emails else f"{payload.userName}@elixir.internal"
    external_id = payload.externalId or str(uuid.uuid4())

    # Check for duplicate
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        (User.email == email_val) | (User.username == payload.userName),
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with username '{payload.userName}' or email '{email_val}' already exists",
        )

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        external_id=external_id,
        username=payload.userName,
        email=email_val,
        first_name=payload.name.givenName if payload.name else None,
        last_name=payload.name.familyName if payload.name else None,
        roles=payload.roles or ["KnowledgeWorker"],
        department=payload.department,
        is_active=payload.active,
    )
    db.add(user)
    await db.flush()

    scim_obj = user_to_scim_dict(user, request)
    response.headers["Location"] = scim_obj["meta"]["location"]
    return scim_obj


@scim_router.get("/Users/{user_id}", response_model=dict[str, Any])
async def get_scim_user(
    user_id: UUID,
    request: Request,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve a single SCIM user by ID."""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found"
        )

    return user_to_scim_dict(user, request)


@scim_router.put("/Users/{user_id}", response_model=dict[str, Any])
async def update_scim_user(
    user_id: UUID,
    payload: ScimUserCreate,
    request: Request,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Replace an existing SCIM user by ID."""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found"
        )

    if payload.name:
        user.first_name = payload.name.givenName
        user.last_name = payload.name.familyName
    if payload.emails:
        user.email = payload.emails[0].value
    user.username = payload.userName
    user.is_active = payload.active
    if payload.roles:
        user.roles = payload.roles
    if payload.department:
        user.department = payload.department

    await db.flush()
    return user_to_scim_dict(user, request)


@scim_router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scim_user(
    user_id: UUID,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete or deactivate a SCIM user by ID."""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found"
        )

    # In SCIM, deletion or deactivation marks the user inactive
    user.is_active = False
    await db.flush()


# ==============================================================================
# SCIM 2.0 Groups Endpoints
# ==============================================================================


@scim_router.get("/Groups", response_model=dict[str, Any])
async def list_scim_groups(
    request: Request,
    startIndex: int = Query(1, ge=1),
    count: int = Query(50, ge=1, le=100),
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List groups for the authenticated tenant with SCIM 2.0 pagination."""
    count_stmt = select(func.count(Group.id)).where(Group.tenant_id == tenant_id)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = startIndex - 1
    stmt = (
        select(Group)
        .where(Group.tenant_id == tenant_id)
        .order_by(Group.created_at.desc())
        .offset(offset)
        .limit(count)
    )
    groups = (await db.execute(stmt)).scalars().all()

    resources = [group_to_scim_dict(g, request) for g in groups]
    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": total,
        "startIndex": startIndex,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


@scim_router.post("/Groups", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
async def create_scim_group(
    payload: ScimGroupCreate,
    request: Request,
    response: Response,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new group and assign members via SCIM 2.0."""
    stmt = select(Group).where(Group.tenant_id == tenant_id, Group.name == payload.displayName)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Group '{payload.displayName}' already exists",
        )

    group = Group(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=payload.displayName,
    )
    db.add(group)
    await db.flush()

    members: list[User] = []
    for item in payload.members:
        try:
            uid = UUID(item.value)
            user_stmt = select(User).where(User.id == uid, User.tenant_id == tenant_id)
            user = (await db.execute(user_stmt)).scalar_one_or_none()
            if user:
                membership = GroupMember(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    group_id=group.id,
                    user_id=user.id,
                )
                db.add(membership)
                members.append(user)
        except ValueError:
            pass

    await db.flush()

    scim_obj = group_to_scim_dict(group, request, members)
    response.headers["Location"] = scim_obj["meta"]["location"]
    return scim_obj


@scim_router.get("/Groups/{group_id}", response_model=dict[str, Any])
async def get_scim_group(
    group_id: UUID,
    request: Request,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve group details and membership by ID."""
    stmt = select(Group).where(Group.id == group_id, Group.tenant_id == tenant_id)
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Group '{group_id}' not found"
        )

    members_stmt = (
        select(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    members = (await db.execute(members_stmt)).scalars().all()

    return group_to_scim_dict(group, request, list(members))


@scim_router.delete("/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scim_group(
    group_id: UUID,
    tenant_id: UUID = Depends(verify_scim_bearer_token),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a SCIM group by ID."""
    stmt = select(Group).where(Group.id == group_id, Group.tenant_id == tenant_id)
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Group '{group_id}' not found"
        )

    await db.delete(group)
    await db.flush()
