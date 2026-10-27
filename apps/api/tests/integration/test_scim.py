"""SCIM 2.0 Integration Tests (RFC 7643 / RFC 7644) with Per-Tenant Bearer Authentication.

Tests run against real PostgreSQL 16 with RLS.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from apps.api.app.identity.models import ScimBearerToken
from apps.api.app.identity.scim import hash_token
from apps.api.app.identity.service import ACROCORP_TENANT_ID, FINCORP_TENANT_ID
from apps.api.app.main import app
from apps.api.app.tenancy.database import AsyncSessionFactory


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def acrocorp_scim_token():
    """Seed an active SCIM bearer token for AcroCorp tenant."""
    raw_token = f"scim_test_acrocorp_{uuid.uuid4().hex}"
    digest = hash_token(raw_token)
    token_id = uuid.uuid4()

    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(ACROCORP_TENANT_ID)},
        )
        token_record = ScimBearerToken(
            id=token_id,
            tenant_id=ACROCORP_TENANT_ID,
            description="AcroCorp Okta SCIM Token",
            token_hash=digest,
            is_active=True,
        )
        db.add(token_record)
        await db.commit()

    return raw_token


@pytest.fixture
async def fincorp_scim_token():
    """Seed an active SCIM bearer token for FinCorp tenant."""
    raw_token = f"scim_test_fincorp_{uuid.uuid4().hex}"
    digest = hash_token(raw_token)
    token_id = uuid.uuid4()

    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(FINCORP_TENANT_ID)},
        )
        token_record = ScimBearerToken(
            id=token_id,
            tenant_id=FINCORP_TENANT_ID,
            description="FinCorp Entra SCIM Token",
            token_hash=digest,
            is_active=True,
        )
        db.add(token_record)
        await db.commit()

    return raw_token


@pytest.mark.asyncio
async def test_scim_unauthenticated_request_rejected():
    """SCIM endpoints must strictly reject requests missing valid Bearer authorization."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No header
        res1 = await client.get("/api/v1/scim/v2/Users")
        assert res1.status_code == 401
        assert "WWW-Authenticate" in res1.headers

        # Invalid token
        res2 = await client.get(
            "/api/v1/scim/v2/Users",
            headers={"Authorization": "Bearer totally_bogus_token_123"},
        )
        assert res2.status_code == 401


@pytest.mark.asyncio
async def test_scim_users_crud_lifecycle(acrocorp_scim_token):
    """Full lifecycle: create user, get user, update user, search users, delete user."""
    auth_header = {"Authorization": f"Bearer {acrocorp_scim_token}"}
    username = f"scim.user.{uuid.uuid4().hex[:6]}"
    email = f"{username}@acrocorp.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create User
        create_payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": username,
            "externalId": f"okta-{uuid.uuid4().hex[:8]}",
            "name": {"givenName": "Jane", "familyName": "Doe"},
            "emails": [{"value": email, "primary": True}],
            "roles": ["KnowledgeWorker", "RecordsManager"],
            "department": "Compliance",
            "active": True,
        }
        res_create = await client.post(
            "/api/v1/scim/v2/Users",
            json=create_payload,
            headers=auth_header,
        )
        assert res_create.status_code == 201, f"Create failed: {res_create.text}"
        user_data = res_create.json()
        user_id = user_data["id"]
        assert user_data["userName"] == username
        assert any(r.get("value") == "RecordsManager" for r in user_data["roles"])

        # 2. Get User by ID
        res_get = await client.get(f"/api/v1/scim/v2/Users/{user_id}", headers=auth_header)
        assert res_get.status_code == 200
        assert res_get.json()["id"] == user_id

        # 3. List Users with filter
        res_list = await client.get(
            f'/api/v1/scim/v2/Users?filter=userName eq "{username}"',
            headers=auth_header,
        )
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["totalResults"] >= 1
        found = [u for u in list_data["Resources"] if u["id"] == user_id]
        assert len(found) == 1

        # 4. Update User (PUT)
        update_payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": username,
            "name": {"givenName": "Janet", "familyName": "Doe"},
            "emails": [{"value": email, "primary": True}],
            "roles": ["TenantAdmin"],
            "department": "Legal",
            "active": True,
        }
        res_update = await client.put(
            f"/api/v1/scim/v2/Users/{user_id}",
            json=update_payload,
            headers=auth_header,
        )
        assert res_update.status_code == 200
        updated = res_update.json()
        assert updated["name"]["givenName"] == "Janet"
        assert any(r.get("value") == "TenantAdmin" for r in updated["roles"])

        # 5. Delete (deactivate) User
        res_del = await client.delete(f"/api/v1/scim/v2/Users/{user_id}", headers=auth_header)
        assert res_del.status_code == 204

        # 6. Verify user is now deactivated
        res_after = await client.get(f"/api/v1/scim/v2/Users/{user_id}", headers=auth_header)
        assert res_after.status_code == 200
        assert res_after.json()["active"] is False


@pytest.mark.asyncio
async def test_scim_groups_crud_with_members(acrocorp_scim_token):
    """Create group, add members, inspect group members, and delete group."""
    auth_header = {"Authorization": f"Bearer {acrocorp_scim_token}"}
    group_name = f"Legal Reviewers {uuid.uuid4().hex[:6]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a user first to be a member
        m_uid = uuid.uuid4().hex[:6]
        user_res = await client.post(
            "/api/v1/scim/v2/Users",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": f"member.{m_uid}",
                "emails": [{"value": f"member.{m_uid}@acrocorp.com", "primary": True}],
                "active": True,
            },
            headers=auth_header,
        )
        assert user_res.status_code == 201
        member_id = user_res.json()["id"]

        # 1. Create Group with Member
        create_payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": group_name,
            "members": [{"value": member_id, "display": "Member 1"}],
        }
        res_group = await client.post(
            "/api/v1/scim/v2/Groups",
            json=create_payload,
            headers=auth_header,
        )
        assert res_group.status_code == 201, f"Create group failed: {res_group.text}"
        group_data = res_group.json()
        group_id = group_data["id"]
        assert group_data["displayName"] == group_name
        assert len(group_data["members"]) == 1
        assert group_data["members"][0]["value"] == member_id

        # 2. Get Group by ID
        get_res = await client.get(f"/api/v1/scim/v2/Groups/{group_id}", headers=auth_header)
        assert get_res.status_code == 200
        assert get_res.json()["displayName"] == group_name
        assert len(get_res.json()["members"]) == 1

        # 3. Delete Group
        del_res = await client.delete(f"/api/v1/scim/v2/Groups/{group_id}", headers=auth_header)
        assert del_res.status_code == 204

        # 4. Verify Group deleted
        get_after = await client.get(f"/api/v1/scim/v2/Groups/{group_id}", headers=auth_header)
        assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_scim_cross_tenant_isolation(acrocorp_scim_token, fincorp_scim_token):
    """AcroCorp SCIM token MUST NOT be able to view, update, or delete FinCorp users."""
    acro_headers = {"Authorization": f"Bearer {acrocorp_scim_token}"}
    fincorp_headers = {"Authorization": f"Bearer {fincorp_scim_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create user in FinCorp
        f_uid = uuid.uuid4().hex[:6]
        fincorp_res = await client.post(
            "/api/v1/scim/v2/Users",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": f"fincorp_exclusive_{f_uid}",
                "emails": [{"value": f"exclusive.{f_uid}@fincorp.com", "primary": True}],
                "active": True,
            },
            headers=fincorp_headers,
        )
        assert fincorp_res.status_code == 201
        fincorp_user_id = fincorp_res.json()["id"]

        # Attempt to access FinCorp user with AcroCorp token: MUST fail with 404
        cross_res = await client.get(
            f"/api/v1/scim/v2/Users/{fincorp_user_id}",
            headers=acro_headers,
        )
        assert cross_res.status_code == 404, f"Cross-tenant leak! Status: {cross_res.status_code}"

        # Attempt to delete FinCorp user with AcroCorp token: MUST fail with 404
        cross_del = await client.delete(
            f"/api/v1/scim/v2/Users/{fincorp_user_id}",
            headers=acro_headers,
        )
        assert cross_del.status_code == 404


@pytest.mark.asyncio
async def test_scim_error_handling_and_group_listing(acrocorp_scim_token):
    """Verify SCIM duplicate 409 conflicts, 404 not founds, and group pagination."""
    auth_header = {"Authorization": f"Bearer {acrocorp_scim_token}"}
    fake_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Non-existent User GET/PUT/DELETE -> 404
        res_get_404 = await client.get(f"/api/v1/scim/v2/Users/{fake_id}", headers=auth_header)
        assert res_get_404.status_code == 404

        res_put_404 = await client.put(
            f"/api/v1/scim/v2/Users/{fake_id}",
            json={"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "userName": "nobody"},
            headers=auth_header,
        )
        assert res_put_404.status_code == 404

        res_del_404 = await client.delete(f"/api/v1/scim/v2/Users/{fake_id}", headers=auth_header)
        assert res_del_404.status_code == 404

        # 2. Non-existent Group GET/DELETE -> 404
        assert (await client.get(f"/api/v1/scim/v2/Groups/{fake_id}", headers=auth_header)).status_code == 404
        assert (await client.delete(f"/api/v1/scim/v2/Groups/{fake_id}", headers=auth_header)).status_code == 404

        # 3. Create User and attempt duplicate -> 409 Conflict
        uname = f"dup.user.{uuid.uuid4().hex[:6]}"
        u_payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": uname,
            "emails": [{"value": f"{uname}@acrocorp.com", "primary": True}],
        }
        res_first = await client.post("/api/v1/scim/v2/Users", json=u_payload, headers=auth_header)
        assert res_first.status_code == 201

        res_second = await client.post("/api/v1/scim/v2/Users", json=u_payload, headers=auth_header)
        assert res_second.status_code == 409

        # 4. List Groups pagination
        g_name = f"Pagination Group {uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/scim/v2/Groups",
            json={"schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"], "displayName": g_name},
            headers=auth_header,
        )
        res_groups = await client.get("/api/v1/scim/v2/Groups?startIndex=1&count=10", headers=auth_header)
        assert res_groups.status_code == 200
        assert res_groups.json()["totalResults"] >= 1
        assert any(g["displayName"] == g_name for g in res_groups.json()["Resources"])

        # 5. Duplicate Group name -> 409 Conflict
        res_dup_group = await client.post(
            "/api/v1/scim/v2/Groups",
            json={"schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"], "displayName": g_name},
            headers=auth_header,
        )
        assert res_dup_group.status_code == 409


@pytest.mark.asyncio
async def test_scim_pagination_and_invalid_auth(acrocorp_scim_token):
    """Test user pagination slice without filter, malformed auth header, and invalid member IDs."""
    auth_header = {"Authorization": f"Bearer {acrocorp_scim_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User pagination without filter
        res_list = await client.get("/api/v1/scim/v2/Users?startIndex=1&count=2", headers=auth_header)
        assert res_list.status_code == 200
        data = res_list.json()
        assert "Resources" in data
        assert data["startIndex"] == 1
        assert len(data["Resources"]) <= 2

        # Non-bearer or malformed authorization header -> 401
        res_bad_auth = await client.get(
            "/api/v1/scim/v2/Users",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert res_bad_auth.status_code == 401

        # Group creation with non-UUID member id string (handled safely via ValueError)
        res_bad_member = await client.post(
            "/api/v1/scim/v2/Groups",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": f"Special Group {uuid.uuid4().hex[:6]}",
                "members": [{"value": "invalid-uuid-format"}],
            },
            headers=auth_header,
        )
        assert res_bad_member.status_code == 201


