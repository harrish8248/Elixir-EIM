"""Unit and Integration Tests for PostgreSQL FTS, pg_trgm fuzzy matching, and Department ACL Trimming."""

import uuid
import pytest
from sqlalchemy import text

from apps.api.app.identity.session import SessionData
from apps.api.app.search.router import search
from apps.api.app.tenancy.database import AsyncSessionFactory


@pytest.mark.asyncio
async def test_search_department_acl_and_fuzzy():
    tenant_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    doc_hr_id = uuid.uuid4()
    doc_fin_id = uuid.uuid4()
    doc_pub_id = uuid.uuid4()

    async with AsyncSessionFactory() as db:
        # 1. Create tenant and workspace
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "ACL Test Corp", "slug": f"acl-test-{uuid.uuid4().hex[:6]}"},
        )
        await db.execute(
            text(
                "INSERT INTO workspaces (id, tenant_id, name) "
                "VALUES (:id, :tenant_id, 'Corporate Workspace')"
            ),
            {"id": str(ws_id), "tenant_id": str(tenant_id)},
        )

        # 2. Insert documents with search_vector trigger
        await db.execute(
            text(
                """
                INSERT INTO documents (
                    id, tenant_id, workspace_id, name, description, classification, department, status,
                    ocr_text, extracted_fields_text
                )
                VALUES
                (
                    :doc_hr_id, :tenant_id, :ws_id, 'Q3 Executive Payroll Summary.pdf', 'Executive compensation review',
                    'CONFIDENTIAL', 'HR', 'active',
                    'Confidential compensation and salary bonuses for executive leadership.',
                    'vendor: AcroCorp HR department: HR total_payroll: 1250000'
                ),
                (
                    :doc_fin_id, :tenant_id, :ws_id, 'Vendor Invoice INV-2026-9021.pdf', 'Cloud datacenter hosting',
                    'CONFIDENTIAL', 'Finance', 'active',
                    'Tax invoice for dedicated hosting clusters and transit connectivity.',
                    'vendor: CloudScale Networks invoice_number: INV-2026-9021 gstin: 27AAPFU0939F1ZV total: 45000'
                ),
                (
                    :doc_pub_id, :tenant_id, :ws_id, 'Global Corporate Code of Conduct.pdf', 'Workplace ethics and policies',
                    'PUBLIC', NULL, 'active',
                    'General workplace guidelines and ethical compliance standards for all employees.',
                    'category: Policy audience: All Employees'
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "ws_id": str(ws_id),
                "doc_hr_id": str(doc_hr_id),
                "doc_fin_id": str(doc_fin_id),
                "doc_pub_id": str(doc_pub_id),
            },
        )
        await db.commit()

        # Maria (HR Analyst) Session
        maria_session = SessionData(
            session_id="test-session-maria",
            user_id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="maria.hr@acrocorp.com",
            username="maria",
            roles=["Employee"],
            department="HR",
            clearance_level=2,  # CONFIDENTIAL
            csrf_token="csrf-token-maria",
            created_at=1000.0,
            last_active_at=1000.0,
            absolute_expiry=2000.0,
        )

        # Raj (Finance Specialist) Session
        raj_session = SessionData(
            session_id="test-session-raj",
            user_id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="raj.finance@acrocorp.com",
            username="raj",
            roles=["Employee"],
            department="Finance",
            clearance_level=2,  # CONFIDENTIAL
            csrf_token="csrf-token-raj",
            created_at=1000.0,
            last_active_at=1000.0,
            absolute_expiry=2000.0,
        )

        # Sarah (Admin / Auditor) Session
        admin_session = SessionData(
            session_id="test-session-admin",
            user_id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="sarah.admin@acrocorp.com",
            username="sarah",
            roles=["Admin"],
            department="Governance",
            clearance_level=3,  # RESTRICTED
            csrf_token="csrf-token-admin",
            created_at=1000.0,
            last_active_at=1000.0,
            absolute_expiry=2000.0,
        )

        # --- TEST 1: Maria (HR) Search Isolation ---
        res_maria_payroll = await search(q="Payroll", session=maria_session, db=db)
        hr_item_ids = [item["id"] for item in res_maria_payroll["items"]]
        assert str(doc_hr_id) in hr_item_ids, "Maria must see HR Payroll document"

        res_maria_fin = await search(q="INV-2026-9021", session=maria_session, db=db)
        assert len(res_maria_fin["items"]) == 0, "Maria must NOT see Finance invoice document (ACL trimmed)"

        # --- TEST 2: Raj (Finance) Search Isolation ---
        res_raj_fin = await search(q="INV-2026-9021", session=raj_session, db=db)
        fin_item_ids = [item["id"] for item in res_raj_fin["items"]]
        assert str(doc_fin_id) in fin_item_ids, "Raj must see Finance invoice document"

        res_raj_hr = await search(q="Payroll", session=raj_session, db=db)
        assert str(doc_hr_id) not in [item["id"] for item in res_raj_hr["items"]], "Raj must NOT see HR Payroll document"

        # --- TEST 3: Public Document Accessible to Both ---
        res_maria_pub = await search(q="Conduct", session=maria_session, db=db)
        assert str(doc_pub_id) in [item["id"] for item in res_maria_pub["items"]]

        res_raj_pub = await search(q="Conduct", session=raj_session, db=db)
        assert str(doc_pub_id) in [item["id"] for item in res_raj_pub["items"]]

        # --- TEST 4: Exact Identifier & GSTIN Matching ---
        res_gstin = await search(q="27AAPFU0939F1ZV", session=raj_session, db=db)
        assert str(doc_fin_id) in [item["id"] for item in res_gstin["items"]]

        # --- TEST 5: Fuzzy Trigram Typo Matching (pg_trgm) ---
        res_fuzzy = await search(q="CludScale", session=raj_session, db=db)
        assert str(doc_fin_id) in [item["id"] for item in res_fuzzy["items"]], "Fuzzy typo 'CludScale' must match 'CloudScale Networks'"

        # --- TEST 6: Admin Cross-Department Visibility ---
        res_admin_hr = await search(q="Payroll", session=admin_session, db=db)
        assert str(doc_hr_id) in [item["id"] for item in res_admin_hr["items"]]

        res_admin_fin = await search(q="INV-2026-9021", session=admin_session, db=db)
        assert str(doc_fin_id) in [item["id"] for item in res_admin_fin["items"]]
