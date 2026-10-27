"""Identity Domain Service: Just-In-Time (JIT) User Provisioning, MFA & Step-Up Verification."""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.identity.models import User
from apps.api.app.identity.session import SessionData
from apps.api.app.platform.errors import AuthenticationError, AuthorizationError
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.models import Tenant, TenantStatus

# Standard Tenant UUIDs for deterministic bootstrapping
ACROCORP_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
FINCORP_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
SYSTEM_TENANT_ID = UUID("00000000-0000-0000-0000-000000000000")


async def get_or_create_tenant_by_slug(
    db: AsyncSession,
    slug: str,
    name: str,
    fixed_id: UUID | None = None,
) -> Tenant:
    """Retrieve or create a tenant record in the database."""
    stmt = select(Tenant).where(Tenant.slug == slug)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    if tenant:
        return tenant

    new_tenant = Tenant(
        id=fixed_id or uuid.uuid4(),
        name=name,
        slug=slug,
        status=TenantStatus.ACTIVE,
        settings={"mfa_required": False, "compliance_profile": "ISO15489"},
    )
    db.add(new_tenant)
    await db.flush()
    logger.info(f"Provisioned new tenant '{name}' (ID: {new_tenant.id}, Slug: {slug})")
    return new_tenant


def resolve_roles_from_claims(claims: dict[str, Any]) -> list[str]:
    """Extract standard enterprise roles from Keycloak realm_access or custom claims."""
    roles: set[str] = set()

    # Keycloak realm roles
    realm_access = claims.get("realm_access", {})
    if isinstance(realm_access, dict):
        realm_roles = realm_access.get("roles", [])
        if isinstance(realm_roles, list):
            roles.update(
                r for r in realm_roles if isinstance(r, str) and not r.startswith("default-roles")
            )

    # Direct roles claim
    direct_roles = claims.get("roles", [])
    if isinstance(direct_roles, list):
        roles.update(r for r in direct_roles if isinstance(r, str))

    # Fallback to KnowledgeWorker if no specific enterprise role assigned
    enterprise_roles = {
        "GlobalAdmin",
        "TenantAdmin",
        "RecordsManager",
        "ComplianceOfficer",
        "KnowledgeWorker",
        "Auditor",
    }
    matched = [r for r in roles if r in enterprise_roles]
    return matched if matched else ["KnowledgeWorker"]


def calculate_clearance_level(roles: list[str]) -> int:
    """Determine ABAC security clearance level based on assigned enterprise roles."""
    if "GlobalAdmin" in roles:
        return 5  # Top Secret / Global Override
    if "TenantAdmin" in roles:
        return 4  # Secret / Tenant Admin
    if "RecordsManager" in roles or "ComplianceOfficer" in roles:
        return 3  # Restricted / Governance
    if "KnowledgeWorker" in roles or "Auditor" in roles:
        return 2  # Confidential
    return 1  # Public


async def provision_user_jit(
    db: AsyncSession,
    claims: dict[str, Any],
    forced_tenant_id: UUID | None = None,
) -> User:
    """
    Just-In-Time (JIT) User Provisioning:
    Inspects verified OIDC claims, identifies or provisions the target tenant,
    and creates or updates the local user profile and assigned roles.
    """
    external_id = claims.get("sub")
    if not external_id:
        raise AuthenticationError(
            "OIDC token missing required 'sub' claim", error_code="MISSING_SUB_CLAIM"
        )

    email = claims.get("email") or f"{external_id}@elixir.internal"
    username = claims.get("preferred_username") or email.split("@")[0]
    first_name = claims.get("given_name")
    last_name = claims.get("family_name")
    roles = resolve_roles_from_claims(claims)
    clearance = calculate_clearance_level(roles)

    # 1. Resolve Target Tenant
    target_tenant_id = forced_tenant_id
    if not target_tenant_id:
        token_tenant = claims.get("tenant_id")
        if token_tenant:
            try:
                target_tenant_id = UUID(str(token_tenant))
            except ValueError:
                pass

    if not target_tenant_id:
        # Domain-based mapping
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain == "acrocorp.com":
            tenant = await get_or_create_tenant_by_slug(
                db, "acrocorp", "AcroCorp Global", ACROCORP_TENANT_ID
            )
            target_tenant_id = tenant.id
        elif domain == "fincorp.com":
            tenant = await get_or_create_tenant_by_slug(
                db, "fincorp", "FinCorp Financial", FINCORP_TENANT_ID
            )
            target_tenant_id = tenant.id
        else:
            tenant = await get_or_create_tenant_by_slug(
                db, "system", "Elixir Platform System", SYSTEM_TENANT_ID
            )
            target_tenant_id = tenant.id

    # Bind PostgreSQL session RLS context to the resolved tenant so RLS WITH CHECK succeeds
    from sqlalchemy import text
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(target_tenant_id)},
    )

    # 2. Lookup existing user by external_id or (tenant_id, email)
    stmt = select(User).where(
        User.tenant_id == target_tenant_id,
        (User.external_id == external_id) | (User.email == email),
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    now = datetime.now(UTC)

    if user is None:
        # Create new JIT user record
        user = User(
            id=uuid.uuid4(),
            tenant_id=target_tenant_id,
            external_id=external_id,
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            roles=roles,
            clearance_level=clearance,
            department=claims.get("department") or "Operations",
            is_active=True,
            last_login_at=now,
        )
        db.add(user)
        logger.info(
            f"JIT Provisioned new user: {email} (ID: {user.id}, Tenant: {target_tenant_id})"
        )
    else:
        # Update existing user attributes and sync roles
        user.last_login_at = now
        user.roles = roles
        user.clearance_level = max(user.clearance_level, clearance)
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        logger.info(f"JIT Synchronized user profile: {email} (Roles: {roles})")

    await db.flush()
    return user


def is_mfa_authenticated(session: SessionData) -> bool:
    """Check if session claims prove Multi-Factor Authentication (MFA)."""
    if "mfa" in [m.lower() for m in session.amr]:
        return True
    return bool(session.acr and session.acr in ["2", "silver", "gold", "urn:mace:incommon:iap:silver"])


def assert_step_up_satisfied(session: SessionData, action_name: str) -> None:
    """
    Enforce step-up MFA for sensitive administrative actions (e.g. lifting legal holds,
    role assignments, cryptographic audit verification).
    """
    if not is_mfa_authenticated(session):
        logger.warning(
            f"Step-up MFA required for user '{session.email}' to perform sensitive action: '{action_name}'"
        )
        raise AuthorizationError(
            f"Multi-Factor Authentication (MFA) step-up required for sensitive operation: {action_name}",
            error_code="STEP_UP_REQUIRED",
        )
