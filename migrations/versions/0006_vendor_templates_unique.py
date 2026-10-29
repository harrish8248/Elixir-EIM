"""0006_vendor_templates_unique

Revision ID: 0006_vendor_templates_unique
Revises: 0005_idp_capture
Create Date: 2026-10-29 11:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_vendor_templates_unique"
down_revision: str | None = "0005_idp_capture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_templates_tenant_vendor_field
        ON vendor_templates (tenant_id, vendor_name, field_name);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_vendor_templates_tenant_vendor_field;")
