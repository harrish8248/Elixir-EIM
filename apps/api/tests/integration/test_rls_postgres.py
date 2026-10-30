"""
Row-Level Security (RLS) Multi-Tenant Isolation Tests against Real PostgreSQL.
Proves that:
1. An application role without superuser privileges enforces RLS.
2. Tenant A cannot read Tenant B rows.
3. Queries with no tenant context set return zero rows.
4. Tenant A inserting a row with Tenant B's ID fails with an RLS WITH CHECK violation.
5. The application's database role has rolsuper=False and rolbypassrls=False.
"""

import os
import uuid

import psycopg
import pytest

# Pytest marker identifying tests that require a live PostgreSQL 16 instance
pytestmark = pytest.mark.postgres

raw_url = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://elixir:elixir_secure_pass@127.0.0.1:5432/elixir_eim",
)
DATABASE_URL = raw_url.replace("postgresql+psycopg://", "postgresql://")


def probe_postgres_login(url: str) -> tuple[str, str]:
    """Connect to PostgreSQL with psycopg, run SELECT current_user, version(), and return result.

    Raises an exception if the host is unreachable, connection times out,
    or credentials fail.
    """
    with psycopg.connect(url, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user, version();")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("SELECT current_user, version() returned no rows")
        return str(row[0]), str(row[1])


@pytest.fixture(scope="module")
def pg_connection():
    """Provides a connection to real PostgreSQL.

    - When REQUIRE_POSTGRES=1 is set (CI or start.ps1 test runs), any failure to connect
      or log in will immediately FAIL the tests with the exact exception text.
    - When REQUIRE_POSTGRES is unset, skips gracefully.
    - Uses real psycopg login with 'SELECT current_user, version()' as the readiness gate.
    """
    require_postgres = os.getenv("REQUIRE_POSTGRES", "0").lower() in ("1", "true", "yes")

    try:
        user, ver = probe_postgres_login(DATABASE_URL)
        print(f"\n[RLS Gate] Verified Postgres login: user='{user}', version='{ver}'")
    except Exception as exc:
        if require_postgres:
            pytest.fail(
                f"REQUIRE_POSTGRES=1 is set, but PostgreSQL login failed with real error: {type(exc).__name__}: {exc}"
            )
        else:
            pytest.skip(
                f"PostgreSQL unreachable or login failed ({type(exc).__name__}: {exc}) and REQUIRE_POSTGRES is not set."
            )

    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    with conn.cursor() as cur:
        # Create non-superuser application role
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'elixir_app_role') THEN
                    CREATE ROLE elixir_app_role WITH LOGIN PASSWORD 'app_secure_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
                END IF;
            END
            $$;
        """)

        # Create isolated test table with RLS enabled and forced
        cur.execute("""
            DROP TABLE IF EXISTS test_rls_documents CASCADE;
            CREATE TABLE test_rls_documents (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                name TEXT NOT NULL
            );

            -- Enable and force Row Level Security
            ALTER TABLE test_rls_documents ENABLE ROW LEVEL SECURITY;
            ALTER TABLE test_rls_documents FORCE ROW LEVEL SECURITY;

            -- Grant permissions to non-superuser application role
            GRANT SELECT, INSERT, UPDATE, DELETE ON test_rls_documents TO elixir_app_role;

            -- Drop existing policy if present
            DROP POLICY IF EXISTS tenant_isolation_policy ON test_rls_documents;

            -- Create strict RLS policy matching tenant_id with session variable
            CREATE POLICY tenant_isolation_policy ON test_rls_documents
                FOR ALL
                TO elixir_app_role
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """)

    yield conn

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS test_rls_documents CASCADE;")
    conn.close()


def test_rls_cross_tenant_isolation_and_check_violations(pg_connection):
    """Test suite proving RLS enforcement for non-superuser application role."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    doc_a_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    # Connect as the non-superuser application role
    app_conn_params = psycopg.conninfo.conninfo_to_dict(DATABASE_URL)
    app_conn_params["user"] = "elixir_app_role"
    app_conn_params["password"] = "app_secure_pass"

    with (
        psycopg.connect(**app_conn_params) as app_conn,
        app_conn.cursor() as cur,
    ):
        # 1. Tenant A context: insert doc A
        cur.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        cur.execute(
            "INSERT INTO test_rls_documents (id, tenant_id, name) VALUES (%s, %s, %s)",
            (doc_a_id, tenant_a, "Tenant A Secret File.pdf"),
        )

        # Verify Tenant A can read doc A
        cur.execute("SELECT id, name FROM test_rls_documents")
        rows_a = cur.fetchall()
        assert len(rows_a) == 1
        assert rows_a[0][0] == doc_a_id

        # 2. Switch to Tenant B context: doc A MUST NOT be visible
        cur.execute(f"SET app.current_tenant_id = '{tenant_b}'")
        cur.execute("SELECT id, name FROM test_rls_documents")
        rows_b_initial = cur.fetchall()
        assert len(rows_b_initial) == 0, (
            "Cross-tenant leakage: Tenant B was able to see Tenant A's row!"
        )

        # Insert doc B under Tenant B
        cur.execute(
            "INSERT INTO test_rls_documents (id, tenant_id, name) VALUES (%s, %s, %s)",
            (doc_b_id, tenant_b, "Tenant B Financials.xlsx"),
        )
        cur.execute("SELECT id, name FROM test_rls_documents")
        rows_b_after = cur.fetchall()
        assert len(rows_b_after) == 1
        assert rows_b_after[0][0] == doc_b_id

        # 3. Query with NO tenant set (RESET): must return 0 rows
        cur.execute("RESET app.current_tenant_id")
        cur.execute("SELECT id, name FROM test_rls_documents")
        rows_none = cur.fetchall()
        assert len(rows_none) == 0, "Security violation: Query without tenant set returned rows!"

        # 4. Tenant A attempts to insert a row belonging to Tenant B: must FAIL RLS WITH CHECK
        cur.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
            cur.execute(
                "INSERT INTO test_rls_documents (id, tenant_id, name) VALUES (%s, %s, %s)",
                (uuid.uuid4(), tenant_b, "Malicious Tampered Document.pdf"),
            )
        assert "violates row-level security policy" in str(exc_info.value)


def test_application_connects_as_non_superuser_with_no_rls_bypass(pg_connection):
    """Proves that the application connection configured in settings.database_url_sync
    runs as a non-superuser role with rolsuper=False and rolbypassrls=False,
    guaranteeing that RLS cannot be silently bypassed.
    """
    from apps.api.app.platform.config import settings

    sync_dsn = settings.database_url_sync.replace("postgresql+psycopg://", "postgresql://")
    with (
        psycopg.connect(sync_dsn) as conn,
        conn.cursor() as cur,
    ):
        # 1. Assert current_user is elixir_app_role
        cur.execute("SELECT current_user;")
        user = cur.fetchone()[0]
        assert user == "elixir_app_role"

        # 2. Query pg_roles to assert rolsuper=False and rolbypassrls=False
        cur.execute(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;"
        )
        role_record = cur.fetchone()
        assert role_record is not None, "Application role record not found in pg_roles"
        rolname, rolsuper, rolbypassrls = role_record

        assert rolname == "elixir_app_role"
        assert rolsuper is False, (
            f"CRITICAL SECURITY FAILURE: Application role '{rolname}' has rolsuper=True!"
        )
        assert rolbypassrls is False, (
            f"CRITICAL SECURITY FAILURE: Application role '{rolname}' has rolbypassrls=True!"
        )


@pytest.mark.asyncio
async def test_fastapi_app_real_engine_connects_as_non_superuser(pg_connection):
    """Proves that the FastAPI app's REAL database engine (from apps.api.app.tenancy.database)
    built directly from settings.database_url connects as elixir_app_role with
    rolsuper=False and rolbypassrls=False.
    """
    from sqlalchemy import text

    from apps.api.app.tenancy.database import engine

    async with engine.connect() as conn:
        res = await conn.execute(
            text(
                "SELECT current_user, rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;"
            )
        )
        row = res.fetchone()
        assert row is not None, "Failed to query pg_roles with app's real engine"
        current_user, rolname, rolsuper, rolbypassrls = row

        assert current_user == "elixir_app_role", (
            f"CRITICAL: App real engine connected as '{current_user}', expected 'elixir_app_role'!"
        )
        assert rolname == "elixir_app_role"
        assert rolsuper is False, (
            f"CRITICAL SECURITY FAILURE: Real app engine role '{rolname}' has rolsuper=True!"
        )
        assert rolbypassrls is False, (
            f"CRITICAL SECURITY FAILURE: Real app engine role '{rolname}' has rolbypassrls=True!"
        )
