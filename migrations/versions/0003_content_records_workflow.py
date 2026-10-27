"""0003_content_records_workflow

Revision ID: 0003_content_records_workflow
Revises: 0002_identity_and_audit_triggers
Create Date: 2026-10-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_content_records_workflow"
down_revision: str | None = "0002_identity_and_audit_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # CONTENT SERVICES
    # -------------------------------------------------------------------------

    # Workspaces (top-level containers)
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False, server_default="INTERNAL"),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_workspaces_tenant", "workspaces", ["tenant_id"])
    op.create_index("ix_workspaces_tenant_name", "workspaces", ["tenant_id", "name"], unique=True)

    # Folders
    op.create_table(
        "folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("folders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_folders_tenant", "folders", ["tenant_id"])
    op.create_index("ix_folders_workspace", "folders", ["workspace_id"])
    op.create_index("ix_folders_parent", "folders", ["parent_id"])

    # Documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False, server_default="INTERNAL"),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("file_extension", sa.String(32), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),  # SHA-256 of file
        sa.Column("storage_key", sa.Text(), nullable=True),  # MinIO object key
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        # Status: uploading, scanning, processing, ready, blocked, failed, trashed
        sa.Column("is_record", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_trashed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkout_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("checkout_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("version_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        # FTS column
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.create_index("ix_documents_tenant", "documents", ["tenant_id"])
    op.create_index("ix_documents_workspace", "documents", ["workspace_id"])
    op.create_index("ix_documents_folder", "documents", ["folder_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_is_trashed", "documents", ["is_trashed"])
    op.create_index("ix_documents_classification", "documents", ["classification"])
    # GIN index for FTS
    op.create_index("ix_documents_search_vector", "documents", ["search_vector"], postgresql_using="gin")

    # Document Versions
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        sa.Column("scan_result", sa.String(32), nullable=True),  # clean, infected, error
        sa.Column("ocr_status", sa.String(32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_doc_versions_document", "document_versions", ["document_id"])
    op.create_index("ix_doc_versions_tenant", "document_versions", ["tenant_id"])

    # Document OCR text
    op.create_table(
        "document_text",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("ocr_engine", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_document_text_document", "document_text", ["document_id"])

    # Document Comments
    op.create_table(
        "document_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_email", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_doc_comments_document", "document_comments", ["document_id"])

    # Document Shares
    op.create_table(
        "document_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shared_with_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shared_with_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("permission_level", sa.String(32), nullable=False, server_default="VIEW"),
        sa.Column("shared_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_doc_shares_document", "document_shares", ["document_id"])

    # -------------------------------------------------------------------------
    # RECORDS & GOVERNANCE
    # -------------------------------------------------------------------------

    # Retention Schedules
    op.create_table(
        "retention_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_code", sa.String(64), nullable=True),
        sa.Column("retention_years", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("classification", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_retention_schedules_tenant", "retention_schedules", ["tenant_id"])

    # Document Retention Links
    op.create_table(
        "document_retention",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("retention_schedules.id"), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disposition_action", sa.String(32), nullable=True),
        sa.Column("disposition_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_doc_retention_document", "document_retention", ["document_id"])

    # Legal Holds
    op.create_table(
        "legal_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("matter_number", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("placed_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("placed_by_email", sa.String(255), nullable=False),
        sa.Column("released_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_legal_holds_tenant", "legal_holds", ["tenant_id"])
    op.create_index("ix_legal_holds_status", "legal_holds", ["status"])

    # Legal Hold Targets (documents under hold)
    op.create_table(
        "legal_hold_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hold_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("legal_holds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_hold_targets_hold", "legal_hold_targets", ["hold_id"])
    op.create_index("ix_hold_targets_document", "legal_hold_targets", ["document_id"])
    op.create_index("uq_hold_targets", "legal_hold_targets", ["hold_id", "document_id"], unique=True)

    # -------------------------------------------------------------------------
    # WORKFLOW & APPROVALS
    # -------------------------------------------------------------------------

    # Workflow Tasks (approval requests)
    op.create_table(
        "workflow_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(64), nullable=False, server_default="approval"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        # pending, approved, rejected, cancelled
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_email", sa.String(255), nullable=False),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_email", sa.String(255), nullable=True),
        sa.Column("decision_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_by_email", sa.String(255), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_tasks_tenant", "workflow_tasks", ["tenant_id"])
    op.create_index("ix_workflow_tasks_document", "workflow_tasks", ["document_id"])
    op.create_index("ix_workflow_tasks_assigned", "workflow_tasks", ["assigned_to_id"])
    op.create_index("ix_workflow_tasks_status", "workflow_tasks", ["status"])

    # -------------------------------------------------------------------------
    # FTS TRIGGER for documents
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.department, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(NEW.classification, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER documents_search_vector_trigger
        BEFORE INSERT OR UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents")
    op.execute("DROP FUNCTION IF EXISTS documents_search_vector_update()")
    op.drop_table("legal_hold_targets")
    op.drop_table("legal_holds")
    op.drop_table("document_retention")
    op.drop_table("retention_schedules")
    op.drop_table("workflow_tasks")
    op.drop_table("document_shares")
    op.drop_table("document_comments")
    op.drop_table("document_text")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("folders")
    op.drop_table("workspaces")
