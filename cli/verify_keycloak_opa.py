import httpx


def verify_keycloak() -> None:

    print("=== 1. KEYCLOAK REALM & ROLES/USERS VERIFICATION ===")
    base_url = "http://127.0.0.1:8080"

    # 1. Realm discovery endpoint
    r = httpx.get(f"{base_url}/realms/elixir/.well-known/openid-configuration", timeout=10)
    assert r.status_code == 200, f"Realm openid config failed: {r.status_code}"
    print("[OK] Realm 'elixir' OpenID configuration online.")
    print(f"     Issuer: {r.json()['issuer']}")
    print(f"     Token Endpoint: {r.json()['token_endpoint']}")

    # 2. Authenticate as Master Admin
    token_resp = httpx.post(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": "admin",
            "password": "admin_secure_pass",
        },
        timeout=10,
    )
    assert token_resp.status_code == 200, f"Admin login failed: {token_resp.text}"
    admin_token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. List Roles in 'elixir' realm
    roles_resp = httpx.get(f"{base_url}/admin/realms/elixir/roles", headers=headers, timeout=10)
    assert roles_resp.status_code == 200
    roles = [r["name"] for r in roles_resp.json() if not r["name"].startswith("default-roles")]
    print(f"[OK] Imported Realm Roles ({len(roles)}):")
    for role in sorted(roles):
        print(f"     - {role}")

    # 4. List Users in 'elixir' realm
    users_resp = httpx.get(f"{base_url}/admin/realms/elixir/users", headers=headers, timeout=10)
    assert users_resp.status_code == 200
    users = users_resp.json()
    print(f"[OK] Imported Users ({len(users)}):")
    for u in users:
        print(
            f"     - Username: {u.get('username')}, Email: {u.get('email')}, Enabled: {u.get('enabled')}"
        )


def verify_opa() -> None:

    print("\n=== 2. OPA HEALTH & POLICY QUERY VERIFICATION ===")
    opa_base = "http://127.0.0.1:8181"

    # 1. Health endpoint
    health_resp = httpx.get(f"{opa_base}/health", timeout=5)
    assert health_resp.status_code == 200, f"OPA health check failed: {health_resp.status_code}"
    print(f"[OK] OPA Health Endpoint (HTTP {health_resp.status_code}): healthy")

    # 2. Query 1: GlobalAdmin allowed
    admin_input = {
        "input": {
            "user": {"roles": ["GlobalAdmin"], "tenant_id": "00000000-0000-0000-0000-000000000001"},
            "action": "any:action",
            "resource": {"tenant_id": "00000000-0000-0000-0000-000000000001"},
        }
    }
    q1 = httpx.post(f"{opa_base}/v1/data/elixir/authz/allow", json=admin_input, timeout=5)
    assert q1.status_code == 200
    print(f"[OK] Policy Query (GlobalAdmin): allow = {q1.json().get('result')} (Expected: True)")

    # 3. Query 2: Standard user unauthorized action
    unauthorized_input = {
        "input": {
            "user": {
                "roles": ["KnowledgeWorker"],
                "tenant_id": "00000000-0000-0000-0000-000000000001",
            },
            "action": "records:destroy",
            "resource": {"tenant_id": "00000000-0000-0000-0000-000000000001"},
        }
    }
    q2 = httpx.post(f"{opa_base}/v1/data/elixir/authz/allow", json=unauthorized_input, timeout=5)
    assert q2.status_code == 200
    print(
        f"[OK] Policy Query (KnowledgeWorker -> records:destroy): allow = {q2.json().get('result')} (Expected: False)"
    )


if __name__ == "__main__":
    verify_keycloak()
    verify_opa()
