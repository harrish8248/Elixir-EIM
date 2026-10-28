"""0004_document_text_ocr

Revision ID: 0004_document_text_ocr
Revises: 0003_content_records_workflow
Create Date: 2026-10-28 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_document_text_ocr"
down_revision: str | None = "0003_content_records_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable RLS on document_text
    op.execute("ALTER TABLE document_text ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'document_text' AND policyname = 'document_text_tenant_isolation'
            ) THEN
                CREATE POLICY document_text_tenant_isolation ON document_text
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            END IF;
        END $$;
        """
    )
    op.execute("GRANT ALL ON document_text TO elixir_app_role;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_text_tenant_id ON document_text (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_text_status ON document_text (status);")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_text_tenant_isolation ON document_text;")
    op.execute("ALTER TABLE document_text DISABLE ROW LEVEL SECURITY;")
