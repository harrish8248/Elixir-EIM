"""
Row-Level Security (RLS) Multi-Tenant Isolation Tests against Real PostgreSQL.
Proves that:
1. An application role without superuser privileges enforces RLS.
2. Tenant A cannot read Tenant B rows.
3. Queries with no tenant context set return zero rows.
4. Tenant A inserting a row with Tenant B's ID fails with an RLS WITH CHECK violation.
"""

import os
import uuid
import pytest
import psycopg

# Pytest marker identifying tests that require a live PostgreSQL 16 instance
pytestmark = pytest.mark.postgres

DATABASE_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://elixir:elixir_secure_pass@localhost:5432/elixir_eim"
)


def is_postgres_available() -> bool:
    """Check whether a real PostgreSQL database is reachable."""
    try:
        conn = psycopg.connect(DATABASE_URL, connect_timeout=1)
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def pg_connection():
    """Provides a connection to real PostgreSQL; skips if database is not reachable."""
    if not is_postgres_available():
        pytest.skip("PostgreSQL 16 is not reachable. Run with Docker or in CI.")

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
    """
    Test suite proving RLS enforcement for non-superuser application role.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    doc_a_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    # Connect as the non-superuser application role
    app_conn_params = psycopg.conninfo.conninfo_to_dict(DATABASE_URL)
    app_conn_params["user"] = "elixir_app_role"
    app_conn_params["password"] = "app_secure_pass"

    with psycopg.connect(**app_conn_params) as app_conn:
        with app_conn.cursor() as cur:
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
            assert len(rows_b_initial) == 0, "Cross-tenant leakage: Tenant B was able to see Tenant A's row!"

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
