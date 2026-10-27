#!/usr/bin/env python3
"""
Elixir EIM Demo Seed Script
Seeds demo tenant, users, workspaces, documents, legal holds, retention schedules,
workflow tasks, and audit events for the team lead demo.

Usage:
    python scripts/seed_demo.py [--reset]
"""

import asyncio
import hashlib
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Database URL for migration owner (can create/manage all data)
DATABASE_URL = "postgresql+asyncpg://elixir:elixir_secure_pass@localhost:5432/elixir_eim"

# -------------------------------------------------------------------------
# Demo data constants
# -------------------------------------------------------------------------
DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEMO_TENANT_SLUG = "acrocorp"

DEMO_USERS = [
    {
        "id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
        "external_id": "sarah.chen@acrocorp.com",
        "email": "sarah.chen@acrocorp.com",
        "username": "sarah.chen",
        "first_name": "Sarah",
        "last_name": "Chen",
        "roles": ["RecordsManager", "Admin", "Auditor"],
        "department": "Finance",
        "clearance_level": 3,  # RESTRICTED
    },
    {
        "id": uuid.UUID("20000000-0000-0000-0000-000000000002"),
        "external_id": "raj.patel@acrocorp.com",
        "email": "raj.patel@acrocorp.com",
        "username": "raj.patel",
        "first_name": "Raj",
        "last_name": "Patel",
        "roles": ["Employee"],
        "department": "Finance",
        "clearance_level": 2,  # CONFIDENTIAL
    },
    {
        "id": uuid.UUID("20000000-0000-0000-0000-000000000003"),
        "external_id": "maria.santos@acrocorp.com",
        "email": "maria.santos@acrocorp.com",
        "username": "maria.santos",
        "first_name": "Maria",
        "last_name": "Santos",
        "roles": ["Employee"],
        "department": "HR",
        "clearance_level": 1,  # INTERNAL
    },
    {
        "id": uuid.UUID("20000000-0000-0000-0000-000000000004"),
        "external_id": "alex.auditor@acrocorp.com",
        "email": "alex.auditor@acrocorp.com",
        "username": "alex.auditor",
        "first_name": "Alex",
        "last_name": "Auditor",
        "roles": ["Auditor"],
        "department": "Compliance",
        "clearance_level": 3,
    },
    {
        "id": uuid.UUID("20000000-0000-0000-0000-000000000005"),
        "external_id": "admin@acrocorp.com",
        "email": "admin@acrocorp.com",
        "username": "admin",
        "first_name": "System",
        "last_name": "Admin",
        "roles": ["Admin"],
        "department": "IT",
        "clearance_level": 3,
    },
]

DEMO_WORKSPACE_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
DEMO_HR_WORKSPACE_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
DEMO_FOLDER_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
DEMO_HR_FOLDER_ID = uuid.UUID("40000000-0000-0000-0000-000000000002")

DEMO_DOCS = [
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000001"),
        "workspace_id": DEMO_WORKSPACE_ID,
        "folder_id": DEMO_FOLDER_ID,
        "name": "Q3 2026 Finance Report.pdf",
        "description": "Quarterly financial report with revenue, expenses and projections",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 245760,
        "status": "ready",
        "is_record": True,
        "created_by_id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000002"),
        "workspace_id": DEMO_WORKSPACE_ID,
        "folder_id": DEMO_FOLDER_ID,
        "name": "Vendor MSA — Acme Corp.pdf",
        "description": "Master Service Agreement with Acme Corporation, signed 2024",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 512000,
        "status": "ready",
        "is_record": True,
        "created_by_id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000003"),
        "workspace_id": DEMO_WORKSPACE_ID,
        "folder_id": DEMO_FOLDER_ID,
        "name": "Invoice INV-2026-0892.pdf",
        "description": "Finance department invoice for Q3 services",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 98304,
        "status": "ready",
        "is_record": False,
        "created_by_id": uuid.UUID("20000000-0000-0000-0000-000000000002"),
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000004"),
        "workspace_id": DEMO_HR_WORKSPACE_ID,
        "folder_id": DEMO_HR_FOLDER_ID,
        "name": "HR Policy Handbook 2026.pdf",
        "description": "Employee handbook and HR policies for 2026",
        "classification": "INTERNAL",
        "department": "HR",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 1048576,
        "status": "ready",
        "is_record": True,
        "created_by_id": uuid.UUID("20000000-0000-0000-0000-000000000003"),
    },
    {
        "id": uuid.UUID("50000000-0000-0000-0000-000000000005"),
        "workspace_id": DEMO_WORKSPACE_ID,
        "folder_id": None,
        "name": "Public Annual Report 2025.pdf",
        "description": "Annual report for public disclosure",
        "classification": "PUBLIC",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 3145728,
        "status": "ready",
        "is_record": True,
        "created_by_id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
    },
]

DEMO_HOLD_ID = uuid.UUID("60000000-0000-0000-0000-000000000001")
DEMO_RETENTION_SCHEDULE_ID = uuid.UUID("70000000-0000-0000-0000-000000000001")
DEMO_TASK_ID = uuid.UUID("80000000-0000-0000-0000-000000000001")


async def reset_demo(session: AsyncSession) -> None:
    """Remove all demo data."""
    print("Resetting demo data...")
    await session.execute(text("DELETE FROM workflow_tasks WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM legal_hold_targets WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM legal_holds WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM retention_schedules WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM document_shares WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM document_comments WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM document_versions WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM documents WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM folders WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM workspaces WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM group_members WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM groups WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM users WHERE tenant_id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(DEMO_TENANT_ID)})
    await session.commit()
    print("Demo data reset complete.")


async def seed_demo(session: AsyncSession) -> None:
    """Seed complete demo dataset."""
    print("Seeding demo data...")

    # 1. Tenant
    print("  -> Creating tenant...")
    await session.execute(text("""
        INSERT INTO tenants (id, name, slug, status, settings)
        VALUES (:id, :name, :slug, 'ACTIVE', '{"plan": "enterprise", "max_users": 500}')
        ON CONFLICT (id) DO NOTHING
    """), {"id": str(DEMO_TENANT_ID), "name": "AcroCorp Global (US-East)", "slug": DEMO_TENANT_SLUG})

    # 2. Users
    print("  -> Creating users...")
    for u in DEMO_USERS:
        import json
        await session.execute(text("""
            INSERT INTO users (id, tenant_id, external_id, email, username, first_name, last_name,
                               roles, department, clearance_level, is_active)
            VALUES (:id, :tenant_id, :external_id, :email, :username, :first_name, :last_name,
                    :roles, :department, :clearance_level, true)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": str(u["id"]),
            "tenant_id": str(DEMO_TENANT_ID),
            "external_id": u["external_id"],
            "email": u["email"],
            "username": u["username"],
            "first_name": u["first_name"],
            "last_name": u["last_name"],
            "roles": json.dumps(u["roles"]),
            "department": u["department"],
            "clearance_level": u["clearance_level"],
        })

    # 3. Workspaces
    print("  -> Creating workspaces...")
    await session.execute(text("""
        INSERT INTO workspaces (id, tenant_id, name, description, owner_id, classification, department)
        VALUES (:id, :tid, :name, :desc, :owner, :cls, :dept)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_WORKSPACE_ID), "tid": str(DEMO_TENANT_ID),
        "name": "Global Operations", "desc": "Finance, contracts, and treasury documents",
        "owner": str(DEMO_USERS[0]["id"]), "cls": "CONFIDENTIAL", "dept": "Finance",
    })
    await session.execute(text("""
        INSERT INTO workspaces (id, tenant_id, name, description, owner_id, classification, department)
        VALUES (:id, :tid, :name, :desc, :owner, :cls, :dept)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_HR_WORKSPACE_ID), "tid": str(DEMO_TENANT_ID),
        "name": "Human Resources", "desc": "HR policies, personnel records, and onboarding",
        "owner": str(DEMO_USERS[2]["id"]), "cls": "INTERNAL", "dept": "HR",
    })

    # 4. Folders
    print("  -> Creating folders...")
    await session.execute(text("""
        INSERT INTO folders (id, tenant_id, workspace_id, parent_id, name, path, created_by_id)
        VALUES (:id, :tid, :ws, NULL, :name, :path, :creator)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_FOLDER_ID), "tid": str(DEMO_TENANT_ID),
        "ws": str(DEMO_WORKSPACE_ID), "name": "Contracts & MSAs",
        "path": "/Contracts & MSAs", "creator": str(DEMO_USERS[0]["id"]),
    })
    await session.execute(text("""
        INSERT INTO folders (id, tenant_id, workspace_id, parent_id, name, path, created_by_id)
        VALUES (:id, :tid, :ws, NULL, :name, :path, :creator)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_HR_FOLDER_ID), "tid": str(DEMO_TENANT_ID),
        "ws": str(DEMO_HR_WORKSPACE_ID), "name": "Policies",
        "path": "/Policies", "creator": str(DEMO_USERS[2]["id"]),
    })

    # 5. Documents
    print("  -> Creating documents...")
    import json
    for doc in DEMO_DOCS:
        fake_hash = hashlib.sha256(str(doc["id"]).encode()).hexdigest()
        await session.execute(text("""
            INSERT INTO documents (id, tenant_id, workspace_id, folder_id, name, description,
                classification, department, mime_type, file_extension, size_bytes, content_hash,
                storage_key, status, is_record, created_by_id, tags, metadata)
            VALUES (:id, :tid, :ws, :folder, :name, :desc, :cls, :dept,
                    :mime, :ext, :size, :hash, :storage_key, :status, :is_record, :creator, '[]', '{}')
            ON CONFLICT DO NOTHING
        """), {
            "id": str(doc["id"]),
            "tid": str(DEMO_TENANT_ID),
            "ws": str(doc["workspace_id"]),
            "folder": str(doc["folder_id"]) if doc["folder_id"] else None,
            "name": doc["name"],
            "desc": doc.get("description"),
            "cls": doc["classification"],
            "dept": doc.get("department"),
            "mime": doc.get("mime_type"),
            "ext": doc.get("file_extension"),
            "size": doc.get("size_bytes"),
            "hash": fake_hash,
            "storage_key": f"tenants/{DEMO_TENANT_ID}/documents/{doc['id']}/{doc['name']}",
            "status": doc["status"],
            "is_record": doc.get("is_record", False),
            "creator": str(doc.get("created_by_id", DEMO_USERS[0]["id"])),
        })

        # Create v1 for each document
        ver_id = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO document_versions (id, tenant_id, document_id, version_number, name,
                mime_type, size_bytes, content_hash, storage_key, status, scan_result, created_by_id)
            VALUES (:id, :tid, :doc_id, 1, :name, :mime, :size, :hash, :storage_key, 'ready', 'clean', :creator)
            ON CONFLICT DO NOTHING
        """), {
            "id": str(ver_id), "tid": str(DEMO_TENANT_ID), "doc_id": str(doc["id"]),
            "name": doc["name"], "mime": doc.get("mime_type"), "size": doc.get("size_bytes"),
            "hash": fake_hash,
            "storage_key": f"tenants/{DEMO_TENANT_ID}/documents/{doc['id']}/{doc['name']}",
            "creator": str(doc.get("created_by_id", DEMO_USERS[0]["id"])),
        })

        await session.execute(text("""
            UPDATE documents SET current_version_id = :ver_id WHERE id = :doc_id
        """), {"ver_id": str(ver_id), "doc_id": str(doc["id"])})

    # 6. Retention Schedule
    print("  -> Creating retention schedule...")
    await session.execute(text("""
        INSERT INTO retention_schedules (id, tenant_id, name, description, schedule_code,
            retention_years, department, classification, is_active, created_by_id)
        VALUES (:id, :tid, :name, :desc, :code, :years, :dept, :cls, true, :creator)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_RETENTION_SCHEDULE_ID),
        "tid": str(DEMO_TENANT_ID),
        "name": "SEC Rule 17a-4 Financial Records",
        "desc": "7-year retention for financial records per SEC Rule 17a-4",
        "code": "SEC-17A4-7YR",
        "years": 7,
        "dept": "Finance",
        "cls": "CONFIDENTIAL",
        "creator": str(DEMO_USERS[0]["id"]),
    })

    # 7. Legal Hold (on finance invoice)
    print("  -> Creating legal hold...")
    await session.execute(text("""
        INSERT INTO legal_holds (id, tenant_id, name, description, matter_number,
            status, placed_by_id, placed_by_email)
        VALUES (:id, :tid, :name, :desc, :matter, 'ACTIVE', :placed_by, :placed_email)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_HOLD_ID),
        "tid": str(DEMO_TENANT_ID),
        "name": "DOJ Civil Inquiry - Case 891",
        "desc": "Department of Justice civil inquiry requires preservation of all Finance Q3 records",
        "matter": "DOJ-CIVIL-891",
        "placed_by": str(DEMO_USERS[0]["id"]),
        "placed_email": "sarah.chen@acrocorp.com",
    })

    # Add Q3 Finance Report and Invoice to hold
    for doc_id in [
        "50000000-0000-0000-0000-000000000001",
        "50000000-0000-0000-0000-000000000003",
    ]:
        await session.execute(text("""
            INSERT INTO legal_hold_targets (id, tenant_id, hold_id, document_id)
            VALUES (:id, :tid, :hold, :doc)
            ON CONFLICT DO NOTHING
        """), {
            "id": str(uuid.uuid4()),
            "tid": str(DEMO_TENANT_ID),
            "hold": str(DEMO_HOLD_ID),
            "doc": doc_id,
        })

    # 8. Workflow approval task (Finance Report -> Raj reviews)
    print("  -> Creating workflow task...")
    await session.execute(text("""
        INSERT INTO workflow_tasks (id, tenant_id, document_id, title, description, task_type, status,
            priority, submitted_by_id, submitted_by_email, assigned_to_id, assigned_to_email)
        VALUES (:id, :tid, :doc, :title, :desc, 'approval', 'pending', 'high',
                :sub_id, :sub_email, :asgn_id, :asgn_email)
        ON CONFLICT DO NOTHING
    """), {
        "id": str(DEMO_TASK_ID),
        "tid": str(DEMO_TENANT_ID),
        "doc": "50000000-0000-0000-0000-000000000001",
        "title": "Approve Q3 Finance Report for Board Submission",
        "desc": "Please review and approve the Q3 2026 Finance Report before board submission deadline.",
        "sub_id": str(DEMO_USERS[0]["id"]),
        "sub_email": "sarah.chen@acrocorp.com",
        "asgn_id": str(DEMO_USERS[1]["id"]),
        "asgn_email": "raj.patel@acrocorp.com",
    })

    await session.commit()
    print("\n[OK] Demo data seeded successfully!")
    print("\nDemo Credentials:")
    print("  Tenant: AcroCorp Global (US-East)")
    print("  Sarah Chen  (Records Manager, Finance, RESTRICTED):  sarah.chen / demo123!")
    print("  Raj Patel   (Employee, Finance, CONFIDENTIAL):        raj.patel / demo123!")
    print("  Maria Santos (Employee, HR, INTERNAL):                maria.santos / demo123!")
    print("  Alex Auditor (Auditor, Compliance, RESTRICTED):       alex.auditor / demo123!")
    print("  Admin        (Admin, IT, RESTRICTED):                  admin / demo123!")
    print("\nDemo Credentials:")
    print("  Tenant: AcroCorp Global (US-East)")
    print("  Sarah Chen  (Records Manager, Finance, RESTRICTED):  sarah.chen / demo123!")
    print("  Raj Patel   (Employee, Finance, CONFIDENTIAL):        raj.patel / demo123!")
    print("  Maria Santos (Employee, HR, INTERNAL):                maria.santos / demo123!")
    print("  Alex Auditor (Auditor, Compliance, RESTRICTED):       alex.auditor / demo123!")
    print("  Admin        (Admin, IT, RESTRICTED):                  admin / demo123!")


async def main() -> None:
    reset = "--reset" in sys.argv

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        if reset:
            await reset_demo(session)
        await seed_demo(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
