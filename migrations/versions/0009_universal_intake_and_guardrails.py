"""0009_universal_intake

Revision ID: 0009_universal_intake
Revises: 0008_search_trgm_fields
Create Date: 2026-10-30 16:30:00.000000

"""

from collections.abc import Sequence
from alembic import op

revision: str = "0009_universal_intake"
down_revision: str | None = "0008_search_trgm_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create tenant_guardrails table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_guardrails (
            tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            max_upload_bytes BIGINT NOT NULL DEFAULT 52428800,
            allowed_types JSONB NOT NULL DEFAULT '["pdf","png","jpg","jpeg","docx","xlsx","pptx","odt","csv","tsv","txt","json","xml","html","md","eml","msg","rtf","zip"]'::jsonb,
            blocked_types JSONB NOT NULL DEFAULT '["exe","dll","msi","bat","cmd","ps1","sh","js","vbs","jar","apk","com","scr","docm","xlsm","pptm"]'::jsonb,
            quarantine_types JSONB NOT NULL DEFAULT '["iso","bin","dmg","pkg","7z","tar","gz"]'::jsonb,
            archive_max_depth INTEGER NOT NULL DEFAULT 3,
            archive_max_members INTEGER NOT NULL DEFAULT 500,
            archive_max_ratio FLOAT NOT NULL DEFAULT 100.0,
            clamav_enforce BOOLEAN NOT NULL DEFAULT true,
            strict_magic_bytes BOOLEAN NOT NULL DEFAULT true,
            min_clearance_restricted INTEGER NOT NULL DEFAULT 3,
            sec17a4_mode BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_by VARCHAR(255) NOT NULL DEFAULT 'system'
        )
        """
    )

    op.execute("ALTER TABLE tenant_guardrails ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'tenant_guardrails' AND policyname = 'tenant_guardrails_isolation'
            ) THEN
                CREATE POLICY tenant_guardrails_isolation ON tenant_guardrails
                    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
            END IF;
        END $$
        """
    )

    # 2. Create quarantine_items table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quarantine_items (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            filename VARCHAR(255) NOT NULL,
            detected_mime VARCHAR(128) NOT NULL,
            size_bytes BIGINT NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            storage_key TEXT,
            reason TEXT NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'QUARANTINED',
            item_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            quarantined_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reviewed_at TIMESTAMPTZ,
            reviewed_by VARCHAR(255)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_quarantine_items_tenant_status ON quarantine_items(tenant_id, status)")
    op.execute("ALTER TABLE quarantine_items ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'quarantine_items' AND policyname = 'quarantine_items_isolation'
            ) THEN
                CREATE POLICY quarantine_items_isolation ON quarantine_items
                    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
            END IF;
        END $$
        """
    )

    # 3. Add columns to documents table
    op.execute(
        """
        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS true_mime_type VARCHAR(128),
            ADD COLUMN IF NOT EXISTS extension_mismatch BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS sensitivity_label VARCHAR(32) NOT NULL DEFAULT 'SAFE',
            ADD COLUMN IF NOT EXISTS classification_reason JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS classification_override JSONB,
            ADD COLUMN IF NOT EXISTS archive_inspection JSONB,
            ADD COLUMN IF NOT EXISTS scan_status VARCHAR(32) NOT NULL DEFAULT 'clean',
            ADD COLUMN IF NOT EXISTS scan_details TEXT
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_sensitivity ON documents(tenant_id, sensitivity_label)")

    # 4. Pre-populate tenant_guardrails for all existing tenants
    op.execute(
        """
        INSERT INTO tenant_guardrails (tenant_id)
        SELECT id FROM tenants
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS quarantine_items")
    op.execute("DROP TABLE IF EXISTS tenant_guardrails")
    op.execute(
        """
        ALTER TABLE documents
            DROP COLUMN IF EXISTS true_mime_type,
            DROP COLUMN IF EXISTS extension_mismatch,
            DROP COLUMN IF EXISTS sensitivity_label,
            DROP COLUMN IF EXISTS classification_reason,
            DROP COLUMN IF EXISTS classification_override,
            DROP COLUMN IF EXISTS archive_inspection,
            DROP COLUMN IF EXISTS scan_status,
            DROP COLUMN IF EXISTS scan_details
        """
    )
