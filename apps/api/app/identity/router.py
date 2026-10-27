"""Authentication and Identity Router: OIDC Authorization Code Flow, PKCE, Sessions, and /me."""

import secrets
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.identity.oidc import oidc_service
from apps.api.app.identity.service import (
    is_mfa_authenticated,
    provision_user_jit,
)
from apps.api.app.identity.session import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    SessionData,
    session_manager,
)
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.context import set_current_tenant_id
from apps.api.app.tenancy.database import get_db_session

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Identity"])


class LoginInitResponse(BaseModel):
    authorization_url: str
    state: str


class CallbackRequest(BaseModel):
    code: str
    state: str


class DirectTokenRequest(BaseModel):
    username: str
    password: str
    tenant_id: UUID | None = None


class UserProfileResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    email: str
    username: str
    roles: list[str]
    department: str | None = None
    clearance_level: int
    is_mfa: bool
    csrf_token: str


async def get_current_session(
    request: Request,
    elixir_session: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: str | None = Header(None, alias="Authorization"),
) -> SessionData:
    """
    Dependency that resolves the active session from either the httpOnly cookie
    or the Authorization Bearer header (supporting API test automation).
    """
    session_id: str | None = None

    if elixir_session:
        session_id = elixir_session
    elif authorization and authorization.startswith("Bearer "):
        token_candidate = authorization.split("Bearer ", 1)[1].strip()
        # If token is a session ID (not a JWT)
        if "." not in token_candidate:
            session_id = token_candidate

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: No active session cookie or bearer token provided.",
        )

    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or been revoked. Please log in again.",
        )

    # Propagate tenant context
    set_current_tenant_id(session.tenant_id)
    return session


@auth_router.get("/login", response_model=LoginInitResponse)
async def init_login(
    redirect_uri: str | None = None,
    acr_values: str | None = None,
) -> LoginInitResponse:
    """
    Initialize OIDC Authorization Code Flow with PKCE.
    Generates cryptographically secure state, nonce, and code_verifier stored in Redis.
    """
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = oidc_service.generate_pkce_pair()

    # Store login state in Redis for 10 minutes
    r = await session_manager.get_redis()
    flow_key = f"elixir:oidc_flow:{state}"
    flow_payload = {
        "nonce": nonce,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri or oidc_service.redirect_uri,
    }
    await r.setex(flow_key, 600, json_dump(flow_payload))

    auth_url = await oidc_service.create_authorization_url(
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        acr_values=acr_values,
    )

    return LoginInitResponse(authorization_url=auth_url, state=state)


@auth_router.post("/callback", response_model=UserProfileResponse)
async def auth_callback(
    payload: CallbackRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    """
    Exchange authorization code for tokens, validate signatures against Keycloak JWKS,
    perform JIT user provisioning, establish Redis session, and set httpOnly cookies.
    """
    r = await session_manager.get_redis()
    flow_key = f"elixir:oidc_flow:{payload.state}"
    raw_flow = await r.get(flow_key)
    if not raw_flow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OIDC state parameter. Please restart login.",
        )
    await r.delete(flow_key)

    flow_data = json_load(str(raw_flow))
    code_verifier = str(flow_data["code_verifier"])
    expected_nonce = str(flow_data["nonce"])

    # Exchange code for tokens
    token_response = await oidc_service.exchange_code_for_tokens(payload.code, code_verifier)
    id_token = token_response.get("id_token")
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing id_token in token response",
        )

    # Full token validation
    claims = await oidc_service.validate_token(id_token, expected_nonce=expected_nonce)

    # In standard Keycloak OIDC, realm_access is embedded in the access_token
    if access_token and "realm_access" not in claims:
        try:
            from jose import jwt as jose_jwt
            at_claims = jose_jwt.get_unverified_claims(access_token)
            if "realm_access" in at_claims:
                claims["realm_access"] = at_claims["realm_access"]
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Optional realm_access extraction skipped: {exc}")

    # JIT Provisioning
    user = await provision_user_jit(db, claims)

    # Extract ACR/AMR claims
    acr = claims.get("acr")
    amr = claims.get("amr") or []
    if isinstance(amr, str):
        amr = [amr]

    # Establish Redis session
    session = await session_manager.create_session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        roles=user.roles,
        department=user.department,
        clearance_level=user.clearance_level,
        acr=acr,
        amr=amr,
        id_token=id_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    # Attach httpOnly session & CSRF cookies
    session_manager.attach_cookies(response, session)

    return UserProfileResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        roles=user.roles,
        department=user.department,
        clearance_level=user.clearance_level,
        is_mfa=is_mfa_authenticated(session),
        csrf_token=session.csrf_token,
    )


@auth_router.post("/token", response_model=UserProfileResponse)
async def direct_token_login(
    payload: DirectTokenRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    """
    Direct token authentication against Keycloak (for integration tests & non-interactive pipelines).
    Performs full JWKS validation, JIT provisioning, and sets session cookies.
    """
    discovery = await oidc_service.get_discovery_config()
    token_endpoint = (
        discovery.get("token_endpoint")
        or f"{oidc_service.issuer_url}/protocol/openid-connect/token"
    )

    data = {
        "grant_type": "password",
        "client_id": oidc_service.client_id,
        "client_secret": oidc_service.client_secret,
        "username": payload.username,
        "password": payload.password,
        "scope": "openid email profile",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(token_endpoint, data=data)
            if res.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid Keycloak credentials: {res.text}",
                )
            token_response = res.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Keycloak unreachable: {exc}"
        ) from exc

    id_token = token_response.get("id_token")
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")

    # Validate ID token with cached JWKS
    claims = await oidc_service.validate_token(id_token)

    if access_token and "realm_access" not in claims:
        try:
            from jose import jwt as jose_jwt
            at_claims = jose_jwt.get_unverified_claims(access_token)
            if "realm_access" in at_claims:
                claims["realm_access"] = at_claims["realm_access"]
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Optional realm_access extraction skipped: {exc}")

    # JIT User Provisioning
    user = await provision_user_jit(db, claims, forced_tenant_id=payload.tenant_id)

    acr = claims.get("acr")
    amr = claims.get("amr") or []

    # Establish Redis session
    session = await session_manager.create_session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        roles=user.roles,
        department=user.department,
        clearance_level=user.clearance_level,
        acr=acr,
        amr=amr,
        id_token=id_token,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    # Attach cookies
    session_manager.attach_cookies(response, session)

    # Record audit event for login
    try:
        from apps.api.app.audit.service import record_audit_event
        await record_audit_event(
            db,
            tenant_id=user.tenant_id,
            actor_id=str(user.id),
            actor_email=user.email,
            action="auth:login:success",
            resource_type="session",
            resource_id=session.session_id,
            outcome="ALLOW",
            reason="Keycloak direct grant token authenticated",
        )
    except Exception as audit_exc:  # noqa: BLE001
        logger.warning(f"Failed to record login audit event: {audit_exc}")

    return UserProfileResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        roles=user.roles,
        department=user.department,
        clearance_level=user.clearance_level,
        is_mfa=is_mfa_authenticated(session),
        csrf_token=session.csrf_token,
    )


@auth_router.get("/me", response_model=UserProfileResponse)
async def get_me(session: SessionData = Depends(get_current_session)) -> UserProfileResponse:
    """Return authenticated user profile, active tenant, and session CSRF token."""
    return UserProfileResponse(
        user_id=session.user_id,
        tenant_id=session.tenant_id,
        email=session.email,
        username=session.username,
        roles=session.roles,
        department=session.department,
        clearance_level=session.clearance_level,
        is_mfa=is_mfa_authenticated(session),
        csrf_token=session.csrf_token,
    )


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionData = Depends(get_current_session),
    csrf_header: str | None = Header(None, alias=CSRF_HEADER_NAME),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Revoke active session in Redis, clear cookies, and trigger backchannel logout if applicable.
    Validates CSRF token to prevent cross-site logout abuse.
    """
    if not session_manager.validate_csrf(session, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed. Missing or invalid X-CSRF-Token header.",
        )

    # Record logout audit event
    try:
        from apps.api.app.audit.service import record_audit_event
        await record_audit_event(
            db,
            tenant_id=session.tenant_id,
            actor_id=str(session.user_id),
            actor_email=session.email,
            action="auth:logout",
            resource_type="session",
            resource_id=session.session_id,
            outcome="ALLOW",
            reason="User voluntary sign out",
        )
    except Exception as audit_exc:  # noqa: BLE001
        logger.warning(f"Failed to record logout audit event: {audit_exc}")

    await session_manager.revoke_session(session.session_id)
    session_manager.clear_cookies(response)


@auth_router.post("/step-up")
async def trigger_step_up(
    action: str = "sensitive_operation",
    session: SessionData = Depends(get_current_session),
) -> dict[str, Any]:
    """
    Trigger Step-Up Authentication challenge.
    Returns step-up status or requires redirect to Keycloak with acr_values=2.
    """
    if is_mfa_authenticated(session):
        return {"step_up_satisfied": True, "message": "MFA is already verified."}

    # Generate step-up authorization URL
    login_init = await init_login(acr_values="2")
    return {
        "step_up_satisfied": False,
        "action": action,
        "message": "Step-up Multi-Factor Authentication required.",
        "authorization_url": login_init.authorization_url,
        "state": login_init.state,
    }


def json_dump(obj: Any) -> str:
    import json

    return json.dumps(obj)


def json_load(raw: str) -> Any:
    import json

    return json.loads(raw)
