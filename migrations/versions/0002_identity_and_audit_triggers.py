"""0002_identity_and_audit_triggers

Revision ID: 0002_identity_and_audit_triggers
Revises: 0001_platform_foundation
Create Date: 2026-10-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity_and_audit_triggers"
down_revision: str | None = "0001_platform_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column(
            "roles", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("clearance_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_tenant_email", "users", ["tenant_id", "email"], unique=True)
    op.create_index(
        "ix_users_tenant_external_id", "users", ["tenant_id", "external_id"], unique=True
    )
    op.create_index("ix_users_tenant_username", "users", ["tenant_id", "username"])

    # 2. Groups Table
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_groups_tenant_name", "groups", ["tenant_id", "name"], unique=True)

    # 3. Group Members Table
    op.create_table(
        "group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("uq_group_members", "group_members", ["group_id", "user_id"], unique=True)
    op.create_index("ix_group_members_tenant", "group_members", ["tenant_id"])

    # 4. SCIM Bearer Tokens Table
    op.create_table(
        "scim_bearer_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_scim_tokens_tenant", "scim_bearer_tokens", ["tenant_id"])

    # 5. PostgreSQL Row-Level Security (RLS) on Identity & Audit tables
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users;")
    op.execute("""
        CREATE POLICY tenant_isolation_users ON users
        AS PERMISSIVE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE groups ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE groups FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_groups ON groups;")
    op.execute("""
        CREATE POLICY tenant_isolation_groups ON groups
        AS PERMISSIVE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE group_members FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_group_members ON group_members;")
    op.execute("""
        CREATE POLICY tenant_isolation_group_members ON group_members
        AS PERMISSIVE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE scim_bearer_tokens ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE scim_bearer_tokens FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_scim_tokens ON scim_bearer_tokens;")
    op.execute("""
        CREATE POLICY tenant_isolation_scim_tokens ON scim_bearer_tokens
        AS PERMISSIVE
        USING (
            current_setting('app.current_tenant_id', true) IS NULL 
            OR current_setting('app.current_tenant_id', true) = ''
            OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_audit_events ON audit_events;")
    op.execute("""
        CREATE POLICY tenant_isolation_audit_events ON audit_events
        AS PERMISSIVE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    # 6. Immutable Audit Log Trigger: Strictly Block UPDATE and DELETE on audit_events
    op.execute("""
        CREATE OR REPLACE FUNCTION block_audit_events_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'CRITICAL SECURITY VIOLATION: audit_events table is strictly append-only. UPDATE and DELETE operations are prohibited by database security policy.';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("DROP TRIGGER IF EXISTS trg_block_audit_events_update ON audit_events;")
    op.execute("""
        CREATE TRIGGER trg_block_audit_events_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION block_audit_events_mutation();
    """)

    op.execute("DROP TRIGGER IF EXISTS trg_block_audit_events_delete ON audit_events;")
    op.execute("""
        CREATE TRIGGER trg_block_audit_events_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION block_audit_events_mutation();
    """)

    # 7. Grant application roles permissions, but explicitly REVOKE UPDATE and DELETE on audit_events
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON users, groups, group_members, scim_bearer_tokens TO elixir_app_role, elixir_app_user;"
    )
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM elixir_app_role;")
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM elixir_app_user;")
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_block_audit_events_delete ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_block_audit_events_update ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS block_audit_events_mutation();")
    op.drop_table("scim_bearer_tokens")
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("users")
