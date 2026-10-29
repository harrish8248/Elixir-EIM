"""0008_search_trgm_fields

Revision ID: 0008_search_trgm_fields
Revises: 0007_ocr_engines_control_center
Create Date: 2026-10-29 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_search_trgm_fields"
down_revision: str | None = "0007_ocr_engines_control_center"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pg_trgm extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Add ocr_text and extracted_fields_text columns to documents
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS ocr_text TEXT,
        ADD COLUMN IF NOT EXISTS extracted_fields_text TEXT;
        """
    )

    # 3. Update documents_search_vector_update function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.extracted_fields_text, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.ocr_text, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.ocr_text, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(NEW.department, '')), 'D') ||
                setweight(to_tsvector('simple', coalesce(NEW.classification, '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # 4. Create trigram GIN indexes for typo tolerance & fuzzy search
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_name_trgm ON documents USING gin (name gin_trgm_ops);")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_fields_trgm ON documents
        USING gin ((coalesce(extracted_fields_text, '')) gin_trgm_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_fields_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_documents_name_trgm;")
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS extracted_fields_text,
        DROP COLUMN IF EXISTS ocr_text;
        """
    )
