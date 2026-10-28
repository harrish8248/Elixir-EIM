"""0005_idp_capture

Revision ID: 0005_idp_capture
Revises: 0004_document_text_ocr
Create Date: 2026-10-28 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_idp_capture"
down_revision: str | None = "0004_document_text_ocr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. capture_jobs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS capture_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
            filename VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            document_type VARCHAR(50) NOT NULL DEFAULT 'invoice',
            classification_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            ocr_engine VARCHAR(50) NOT NULL DEFAULT 'tesseract',
            mean_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            processing_time_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            raw_text TEXT,
            idempotency_key VARCHAR(128) UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 2. extracted_fields
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS extracted_fields (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES capture_jobs(id) ON DELETE CASCADE,
            field_name VARCHAR(100) NOT NULL,
            field_value TEXT,
            normalized_value JSONB,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            page INTEGER NOT NULL DEFAULT 1,
            bbox JSONB,
            extraction_method VARCHAR(50) NOT NULL DEFAULT 'heuristic',
            is_valid BOOLEAN NOT NULL DEFAULT true,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 3. validation_results
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES capture_jobs(id) ON DELETE CASCADE,
            rule_name VARCHAR(100) NOT NULL,
            passed BOOLEAN NOT NULL,
            message TEXT NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'error',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 4. field_corrections
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS field_corrections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES capture_jobs(id) ON DELETE CASCADE,
            field_name VARCHAR(100) NOT NULL,
            original_value TEXT,
            corrected_value TEXT NOT NULL,
            corrected_by UUID REFERENCES users(id) ON DELETE SET NULL,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 5. vendor_templates
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vendor_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            vendor_name VARCHAR(255) NOT NULL,
            field_name VARCHAR(100) NOT NULL,
            rel_x DOUBLE PRECISION NOT NULL,
            rel_y DOUBLE PRECISION NOT NULL,
            rel_w DOUBLE PRECISION NOT NULL,
            rel_h DOUBLE PRECISION NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 6. purchase_orders
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            po_number VARCHAR(100) NOT NULL,
            vendor_name VARCHAR(255) NOT NULL,
            total_amount DOUBLE PRECISION NOT NULL,
            currency VARCHAR(10) NOT NULL DEFAULT 'USD',
            status VARCHAR(50) NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # 7. vendors
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vendors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            tax_id VARCHAR(100),
            status VARCHAR(50) NOT NULL DEFAULT 'approved',
            payment_terms VARCHAR(50) NOT NULL DEFAULT 'Net 30',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # Enable RLS & Isolation Policies on all tables
    tables = [
        "capture_jobs",
        "extracted_fields",
        "validation_results",
        "field_corrections",
        "vendor_templates",
        "purchase_orders",
        "vendors",
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

    op.execute("CREATE INDEX IF NOT EXISTS ix_capture_jobs_status ON capture_jobs (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_capture_jobs_created_at ON capture_jobs (created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_extracted_fields_job_id ON extracted_fields (job_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_validation_results_job_id ON validation_results (job_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vendor_templates_vendor ON vendor_templates (vendor_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchase_orders_po ON purchase_orders (po_number);")


def downgrade() -> None:
    tables = [
        "vendors",
        "purchase_orders",
        "vendor_templates",
        "field_corrections",
        "validation_results",
        "extracted_fields",
        "capture_jobs",
    ]
    for tbl in tables:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_isolation ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
