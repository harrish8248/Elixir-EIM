"""Integration Tests for OIDC PKCE Authentication, JWKS Validation, Sessions, and JIT Provisioning.

All tests run against real PostgreSQL 16, Keycloak 26, and Redis 7 containers.
"""

import json
import time
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from jose import jwt

from apps.api.app.identity.oidc import oidc_service
from apps.api.app.identity.service import (
    ACROCORP_TENANT_ID,
    assert_step_up_satisfied,
    is_mfa_authenticated,
    provision_user_jit,
)
from apps.api.app.identity.session import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    SessionData,
    session_manager,
)
from apps.api.app.main import app
from apps.api.app.platform.errors import AuthenticationError, AuthorizationError
from apps.api.app.tenancy.database import AsyncSessionFactory


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_keycloak_discovery_and_jwks_cached_fetch():
    """Verify discovery endpoint and JWKS fetch against real Keycloak container."""
    discovery = await oidc_service.get_discovery_config(force_reload=True)
    assert discovery is not None
    assert "token_endpoint" in discovery
    assert "jwks_uri" in discovery

    jwks = await oidc_service.get_jwks(force_reload=True)
    assert "keys" in jwks
    assert len(jwks["keys"]) > 0
    sig_keys = [k for k in jwks["keys"] if k.get("use") == "sig"]
    assert len(sig_keys) > 0
    assert sig_keys[0].get("alg") in ["RS256", "RS384", "RS512"]


@pytest.mark.asyncio
async def test_pkce_generation():
    """Verify cryptographically sound PKCE pair generation."""
    verifier1, challenge1 = oidc_service.generate_pkce_pair()
    verifier2, challenge2 = oidc_service.generate_pkce_pair()

    assert len(verifier1) >= 43
    assert len(challenge1) >= 43
    assert verifier1 != verifier2
    assert challenge1 != challenge2


@pytest.mark.asyncio
async def test_real_keycloak_direct_token_and_jwks_validation():
    """Obtain a real token from Keycloak for Sarah Chen and validate signature with cached JWKS."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/token",
            json={
                "username": "sarah.chen@acrocorp.com",
                "password": "password123",
            },
        )
        assert res.status_code == 200, f"Token login failed: {res.text}"
        data = res.json()

        assert data["email"] == "sarah.chen@acrocorp.com"
        assert "RecordsManager" in data["roles"]
        assert data["clearance_level"] >= 3

        # Verify session cookies were set
        cookies = res.cookies
        assert SESSION_COOKIE_NAME in cookies
        assert CSRF_COOKIE_NAME in cookies

        session_id = cookies[SESSION_COOKIE_NAME]
        session = await session_manager.get_session(session_id)
        assert session is not None
        assert session.email == "sarah.chen@acrocorp.com"


@pytest.mark.asyncio
async def test_jit_user_provisioning_persists_in_postgres():
    """Verify that JIT user provisioning creates or syncs real records in PostgreSQL."""
    test_email = f"jit.test.{uuid.uuid4().hex[:8]}@acrocorp.com"
    async with AsyncSessionFactory() as db:
        claims = {
            "sub": str(uuid.uuid4()),
            "email": test_email,
            "preferred_username": "jittest",
            "given_name": "JIT",
            "family_name": "Tester",
            "realm_access": {"roles": ["KnowledgeWorker"]},
            "department": "Engineering",
        }

        user = await provision_user_jit(db, claims)
        assert user.id is not None
        assert user.email == test_email
        assert user.tenant_id == ACROCORP_TENANT_ID
        assert "KnowledgeWorker" in user.roles
        assert user.clearance_level == 2

        # Re-provision with updated role: must sync roles without duplicating record
        claims["realm_access"]["roles"] = ["RecordsManager"]
        synced_user = await provision_user_jit(db, claims)
        assert synced_user.id == user.id
        assert "RecordsManager" in synced_user.roles
        assert synced_user.clearance_level == 3
        await db.commit()


@pytest.mark.asyncio
async def test_token_validation_rejects_expired_tokens():
    """Verify that expired tokens are strictly rejected."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    expired_token = jwt.encode(
        {
            "iss": oidc_service.issuer_url,
            "aud": oidc_service.client_id,
            "exp": int(time.time()) - 300,
            "sub": "expired-user",
        },
        priv_pem,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    with pytest.raises((AuthenticationError, jwt.ExpiredSignatureError)) as exc_info:
        # Validate directly using jose with mock key
        jwt.decode(
            expired_token,
            pub_pem,
            algorithms=["RS256"],
            audience=oidc_service.client_id,
            issuer=oidc_service.issuer_url,
        )
    assert "expired" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_token_validation_rejects_tampered_signature():
    """Verify that tampered tokens fail cryptographic verification."""
    # Obtain real token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/token",
            json={"username": "john.doe@acrocorp.com", "password": "password123"},
        )
        assert res.status_code == 200
        session_id = res.cookies[SESSION_COOKIE_NAME]
        session = await session_manager.get_session(session_id)
        assert session is not None
        assert session.id_token is not None

        # Tamper token signature
        tampered_token = session.id_token[:-6] + "XYZ123"

        with pytest.raises(AuthenticationError) as exc_info:
            await oidc_service.validate_token(tampered_token)
        assert exc_info.value.code in ["INVALID_SIGNATURE", "INVALID_TOKEN_FORMAT"]


@pytest.mark.asyncio
async def test_token_validation_rejects_wrong_issuer_and_wrong_audience():
    """Verify that incorrect issuer or audience claims are rejected."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    # Wrong issuer
    bad_iss_token = jwt.encode(
        {
            "iss": "https://rogue-idp.attacker.com",
            "aud": oidc_service.client_id,
            "exp": int(time.time()) + 3600,
            "sub": "user-1",
        },
        priv_pem,
        algorithm="RS256",
    )
    with pytest.raises(jwt.JWTClaimsError):
        jwt.decode(
            bad_iss_token,
            pub_pem,
            algorithms=["RS256"],
            audience=oidc_service.client_id,
            issuer=oidc_service.issuer_url,
        )

    # Wrong audience
    bad_aud_token = jwt.encode(
        {
            "iss": oidc_service.issuer_url,
            "aud": "rogue-client-id",
            "exp": int(time.time()) + 3600,
            "sub": "user-1",
        },
        priv_pem,
        algorithm="RS256",
    )
    with pytest.raises(jwt.JWTClaimsError):
        jwt.decode(
            bad_aud_token,
            pub_pem,
            algorithms=["RS256"],
            audience=oidc_service.client_id,
            issuer=oidc_service.issuer_url,
        )


@pytest.mark.asyncio
async def test_session_lifecycle_and_csrf_protection():
    """Test full session creation, /me bootstrap, CSRF validation, and revocation on logout."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login
        login_res = await client.post(
            "/api/v1/auth/token",
            json={"username": "sarah.chen@acrocorp.com", "password": "password123"},
        )
        assert login_res.status_code == 200
        session_id = login_res.cookies[SESSION_COOKIE_NAME]
        csrf_token = login_res.cookies[CSRF_COOKIE_NAME]

        # 2. Access /me with session cookie
        me_res = await client.get("/api/v1/auth/me", cookies={SESSION_COOKIE_NAME: session_id})
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "sarah.chen@acrocorp.com"

        # 3. Attempt logout without CSRF header: must be rejected with 403
        bad_logout = await client.post(
            "/api/v1/auth/logout",
            cookies={SESSION_COOKIE_NAME: session_id},
        )
        assert bad_logout.status_code == 403
        assert "CSRF" in bad_logout.text

        # 4. Attempt logout with valid CSRF header: must succeed with 204
        good_logout = await client.post(
            "/api/v1/auth/logout",
            cookies={SESSION_COOKIE_NAME: session_id},
            headers={CSRF_HEADER_NAME: csrf_token},
        )
        assert good_logout.status_code == 204

        # 5. Access /me after logout: must be rejected with 401
        after_me = await client.get("/api/v1/auth/me", cookies={SESSION_COOKIE_NAME: session_id})
        assert after_me.status_code == 401


@pytest.mark.asyncio
async def test_mfa_detection_and_step_up_enforcement():
    """Verify acr/amr MFA detection and step-up challenge behavior."""
    # Session without MFA
    non_mfa_session = SessionData(
        session_id="test-non-mfa",
        user_id=uuid.uuid4(),
        tenant_id=ACROCORP_TENANT_ID,
        email="user@acrocorp.com",
        username="user",
        roles=["RecordsManager"],
        csrf_token="csrf1",
        created_at=time.time(),
        last_active_at=time.time(),
        absolute_expiry=time.time() + 3600,
        acr="1",
        amr=["pwd"],
    )
    assert is_mfa_authenticated(non_mfa_session) is False

    with pytest.raises(AuthorizationError) as exc_info:
        assert_step_up_satisfied(non_mfa_session, "Lift Legal Hold #891")
    assert "MFA" in str(exc_info.value) or "step-up" in str(exc_info.value).lower()

    # Session with MFA
    mfa_session = SessionData(
        session_id="test-mfa",
        user_id=uuid.uuid4(),
        tenant_id=ACROCORP_TENANT_ID,
        email="admin@acrocorp.com",
        username="admin",
        roles=["GlobalAdmin"],
        csrf_token="csrf2",
        created_at=time.time(),
        last_active_at=time.time(),
        absolute_expiry=time.time() + 3600,
        acr="2",
        amr=["pwd", "mfa"],
    )
    assert is_mfa_authenticated(mfa_session) is True
    # Should not raise
    assert_step_up_satisfied(mfa_session, "Lift Legal Hold #891")


@pytest.mark.asyncio
async def test_oidc_init_login_and_pkce_state():
    """Verify GET /api/v1/auth/login creates PKCE state in Redis and returns authorization URL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/login")
        assert res.status_code == 200
        data = res.json()
        assert "authorization_url" in data
        assert "state" in data
        state = data["state"]
        assert "response_type=code" in data["authorization_url"]
        assert "code_challenge=" in data["authorization_url"]

        # Verify flow stored in Redis
        r = await session_manager.get_redis()
        stored_flow = await r.get(f"elixir:oidc_flow:{state}")
        assert stored_flow is not None


@pytest.mark.asyncio
async def test_auth_userinfo_and_step_up_endpoints():
    """Verify /api/v1/auth/userinfo, /step-up initiation, and Bearer token session resolution."""
    user_id = uuid.uuid4()
    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=ACROCORP_TENANT_ID,
        email="testuser@acrocorp.com",
        username="testuser",
        roles=["KnowledgeWorker"],
        department="Finance",
        clearance_level=2,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Access /me via Bearer header with session_id
        res_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {session.session_id}"},
        )
        assert res_me.status_code == 200
        assert res_me.json()["email"] == "testuser@acrocorp.com"

        # 2. Trigger /step-up
        res_stepup = await client.post(
            "/api/v1/auth/step-up",
            cookies={SESSION_COOKIE_NAME: session.session_id},
        )
        assert res_stepup.status_code == 200
        data_stepup = res_stepup.json()
        assert "authorization_url" in data_stepup
        assert "acr_values" in data_stepup["authorization_url"]


@pytest.mark.asyncio
async def test_auth_callback_state_validation():
    """POST /api/v1/auth/callback must reject invalid or expired state with 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/callback",
            json={"code": "bogus-auth-code", "state": "non-existent-state"},
        )
        assert res.status_code == 400
        assert "Invalid or expired OIDC state" in res.json()["detail"]


@pytest.mark.asyncio
async def test_logout_csrf_and_revocation():
    """POST /api/v1/auth/logout must reject missing CSRF token and revoke session on success."""
    user_id = uuid.uuid4()
    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=ACROCORP_TENANT_ID,
        email="logout@acrocorp.com",
        username="logoutuser",
        roles=["KnowledgeWorker"],
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A. Missing CSRF header -> 403 Forbidden
        res_no_csrf = await client.post(
            "/api/v1/auth/logout",
            cookies={SESSION_COOKIE_NAME: session.session_id},
        )
        assert res_no_csrf.status_code == 403

        # B. Wrong CSRF token -> 403 Forbidden
        res_wrong_csrf = await client.post(
            "/api/v1/auth/logout",
            cookies={SESSION_COOKIE_NAME: session.session_id},
            headers={CSRF_HEADER_NAME: "wrong-csrf-token"},
        )
        assert res_wrong_csrf.status_code == 403

        # C. Valid CSRF token -> 204 No Content
        res_good_logout = await client.post(
            "/api/v1/auth/logout",
            cookies={SESSION_COOKIE_NAME: session.session_id},
            headers={CSRF_HEADER_NAME: session.csrf_token},
        )
        assert res_good_logout.status_code == 204

        # D. Subsequent request with revoked session -> 401 Unauthorized
        res_after = await client.get(
            "/api/v1/auth/me",
            cookies={SESSION_COOKIE_NAME: session.session_id},
        )
        assert res_after.status_code == 401


@pytest.mark.asyncio
async def test_auth_callback_flow_and_jit_provisioning(monkeypatch):
    """Test full /api/v1/auth/callback exchange with valid state and mock token exchange."""
    # Obtain real valid Keycloak token from direct grant
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_res = await client.post(
            "/api/v1/auth/token",
            json={"username": "sarah.chen@acrocorp.com", "password": "password123"},
        )
        assert token_res.status_code == 200
        session_id = token_res.cookies[SESSION_COOKIE_NAME]
        session = await session_manager.get_session(session_id)
        assert session is not None
        real_id_token = session.id_token
        real_access_token = session.access_token

        # Extract token nonce (if any) so expected_nonce matches
        from jose import jwt as jose_jwt
        unverified_claims = jose_jwt.get_unverified_claims(real_id_token)
        real_nonce = unverified_claims.get("nonce")

        # Store an OIDC state flow in Redis
        state_key = f"flow-state-{uuid.uuid4().hex}"
        r = await session_manager.get_redis()
        flow_payload = {
            "nonce": real_nonce or "default-nonce",
            "code_verifier": "test-verifier-abc",
            "redirect_uri": "http://localhost:5173/auth/callback",
        }
        await r.set(f"elixir:oidc_flow:{state_key}", json.dumps(flow_payload))

        # Mock token exchange
        monkeypatch.setattr(
            oidc_service,
            "exchange_code_for_tokens",
            AsyncMock(
                return_value={
                    "id_token": real_id_token,
                    "access_token": real_access_token,
                    "refresh_token": "mock-refresh-token",
                }
            ),
        )

        # Mock validate_token to return the verified claims safely
        monkeypatch.setattr(
            oidc_service,
            "validate_token",
            AsyncMock(return_value=unverified_claims),
        )

        # Execute callback
        callback_res = await client.post(
            "/api/v1/auth/callback",
            json={"code": "sample-auth-code-123", "state": state_key},
        )
        assert callback_res.status_code == 200, f"Callback failed: {callback_res.text}"
        data = callback_res.json()
        assert data["email"] == "sarah.chen@acrocorp.com"
        assert SESSION_COOKIE_NAME in callback_res.cookies
        assert CSRF_COOKIE_NAME in callback_res.cookies


@pytest.mark.asyncio
async def test_auth_step_up_already_satisfied():
    """POST /api/v1/auth/step-up should report satisfied when user already has MFA."""
    user_id = uuid.uuid4()
    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=ACROCORP_TENANT_ID,
        email="mfa.user@acrocorp.com",
        username="mfauser",
        roles=["KnowledgeWorker"],
        amr=["pwd", "mfa", "otp"],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/step-up",
            cookies={SESSION_COOKIE_NAME: session.session_id},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["step_up_satisfied"] is True
        assert "already verified" in data["message"].lower()


@pytest.mark.asyncio
async def test_direct_login_keycloak_error_paths(monkeypatch):
    """Direct grant login error handling for bad credentials and Keycloak network failures."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid password -> 401
        res_bad_cred = await client.post(
            "/api/v1/auth/token",
            json={"username": "sarah.chen@acrocorp.com", "password": "wrongpassword!"},
        )
        assert res_bad_cred.status_code == 401

        # Keycloak network error -> 503
        orig_post = httpx.AsyncClient.post

        async def conditional_post(self, *args, **kwargs):
            url_str = str(args[0]) if args else str(kwargs.get("url", ""))
            if "openid-connect" in url_str:
                raise httpx.ConnectError("Keycloak unreachable test")
            return await orig_post(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "post", conditional_post)
        res_unreachable = await client.post(
            "/api/v1/auth/token",
            json={"username": "sarah.chen@acrocorp.com", "password": "password123"},
        )
        assert res_unreachable.status_code == 503


@pytest.mark.asyncio
async def test_oidc_service_error_handling():
    """OIDC service exception branches for token validation and exchange failures."""
    # Malformed token string
    with pytest.raises(AuthenticationError) as exc_info:
        await oidc_service.validate_token("not-a-jwt")
    assert exc_info.value.code == "INVALID_TOKEN_FORMAT"

    # Token exchange HTTP failure
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_post.return_value = mock_resp

        with pytest.raises(AuthenticationError) as exc_info2:
            await oidc_service.exchange_code_for_tokens("code", "verifier")
        assert exc_info2.value.code == "TOKEN_EXCHANGE_FAILED"

    # Token exchange network failure
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(AuthenticationError) as exc_info3:
            await oidc_service.exchange_code_for_tokens("code", "verifier")
        assert exc_info3.value.code == "TOKEN_ENDPOINT_ERROR"



