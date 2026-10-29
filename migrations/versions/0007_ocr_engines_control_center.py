"""0007_ocr_engines_control_center

Revision ID: 0007_ocr_engines_control_center
Revises: 0006_vendor_templates_unique
Create Date: 2026-10-29 11:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_ocr_engines_control_center"
down_revision: str | None = "0006_vendor_templates_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. ocr_engine_configs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_engine_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            engine_id VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            is_enabled BOOLEAN NOT NULL DEFAULT true,
            priority INTEGER NOT NULL DEFAULT 10,
            digital_weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            scanned_weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            custom_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_ocr_engine_tenant UNIQUE (tenant_id, engine_id)
        );
        """
    )

    # 2. ocr_routing_policies
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_routing_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT true,
            default_engine VARCHAR(50) NOT NULL DEFAULT 'tesseract',
            fallback_engine VARCHAR(50) NOT NULL DEFAULT 'tesseract',
            rules JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 3. ocr_benchmark_runs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_benchmark_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            engine_id VARCHAR(50) NOT NULL,
            split_name VARCHAR(50) NOT NULL DEFAULT 'dev',
            cer DOUBLE PRECISION,
            wer DOUBLE PRECISION,
            field_f1 DOUBLE PRECISION,
            gstin_accuracy DOUBLE PRECISION,
            pages_per_sec DOUBLE PRECISION,
            metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            run_date TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # RLS & Permissions
    tables = [
        "ocr_engine_configs",
        "ocr_routing_policies",
        "ocr_benchmark_runs",
    ]

    for tbl in tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies WHERE tablename = '{tbl}' AND policyname = '{tbl}_tenant_isolation'
                ) THEN
                    CREATE POLICY {tbl}_tenant_isolation ON {tbl}
                    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
                END IF;
            END $$;
            """
        )
        op.execute(f"GRANT ALL ON {tbl} TO elixir_app_role;")
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{tbl}_tenant_id ON {tbl} (tenant_id);")

    op.execute("CREATE INDEX IF NOT EXISTS ix_ocr_engine_configs_engine ON ocr_engine_configs (engine_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ocr_routing_policies_active ON ocr_routing_policies (tenant_id, is_active);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ocr_benchmark_runs_engine ON ocr_benchmark_runs (engine_id, split_name);")


def downgrade() -> None:
    tables = [
        "ocr_benchmark_runs",
        "ocr_routing_policies",
        "ocr_engine_configs",
    ]
    for tbl in tables:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_isolation ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
