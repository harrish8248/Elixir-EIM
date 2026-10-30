import asyncio
import uuid
from sqlalchemy import text
from apps.api.app.identity.session import SessionData
from apps.api.app.search.router import search
from apps.api.app.tenancy.database import AsyncSessionFactory

async def run_facet_test():
    tenant_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    doc_hr = uuid.uuid4()
    doc_fin = uuid.uuid4()
    doc_pub = uuid.uuid4()

    print("=== RUNNING MULTI-DEPARTMENT SEARCH FACET ACL VERIFICATION ===")
    async with AsyncSessionFactory() as db:
        # Create tenant & workspace
        await db.execute(
            text("INSERT INTO tenants (id, name, slug, status, settings) VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"),
            {"id": str(tenant_id), "name": "Facet Test Corp", "slug": f"facet-test-{uuid.uuid4().hex[:6]}"}
        )
        await db.execute(
            text("INSERT INTO workspaces (id, tenant_id, name) VALUES (:id, :tenant_id, 'Test Workspace')"),
            {"id": str(ws_id), "tenant_id": str(tenant_id)}
        )

        # Insert 3 test docs: HR Confidential, Finance Confidential, Public
        await db.execute(
            text("""
                INSERT INTO documents (id, tenant_id, workspace_id, name, description, classification, department, status, ocr_text, extracted_fields_text)
                VALUES
                (:hr_id, :t_id, :ws_id, 'HR_Compensation_2026.pdf', 'HR confidential doc', 'CONFIDENTIAL', 'HR', 'active', 'employee salary review', 'dept: HR'),
                (:fin_id, :t_id, :ws_id, 'Finance_Quarterly_Pnl.pdf', 'Finance confidential doc', 'CONFIDENTIAL', 'Finance', 'active', 'corporate revenues and taxes', 'dept: Finance'),
                (:pub_id, :t_id, :ws_id, 'Company_Policy_Public.pdf', 'Public handbook', 'PUBLIC', NULL, 'active', 'welcome handbook for all', 'dept: all')
            """),
            {"hr_id": str(doc_hr), "fin_id": str(doc_fin), "pub_id": str(doc_pub), "t_id": str(tenant_id), "ws_id": str(ws_id)}
        )
        await db.commit()

        # Sessions
        maria_hr = SessionData(
            session_id="sess-maria", user_id=uuid.uuid4(), tenant_id=tenant_id,
            email="maria@corp.com", username="maria", roles=["Employee"], department="HR", clearance_level=2,
            csrf_token="csrf", created_at=1.0, last_active_at=1.0, absolute_expiry=100.0
        )
        raj_finance = SessionData(
            session_id="sess-raj", user_id=uuid.uuid4(), tenant_id=tenant_id,
            email="raj@corp.com", username="raj", roles=["Employee"], department="Finance", clearance_level=2,
            csrf_token="csrf", created_at=1.0, last_active_at=1.0, absolute_expiry=100.0
        )

        # Both search for common search query
        query = ""
        res_hr = await search(q=query, session=maria_hr, db=db)
        res_fin = await search(q=query, session=raj_finance, db=db)

        print(f"Query executed: '{query}'")
        print("\n--- HR User (Maria, Dept: HR, Clearance: 2 - CONFIDENTIAL) ---")
        print("Visible document count:", res_hr["total"])
        print("Visible document names:", [d["name"] for d in res_hr["items"]])
        print("Classification facets:", res_hr["facets"]["classifications"])
        print("Department facets:", res_hr["facets"]["departments"])

        print("\n--- Finance User (Raj, Dept: Finance, Clearance: 2 - CONFIDENTIAL) ---")
        print("Visible document count:", res_fin["total"])
        print("Visible document names:", [d["name"] for d in res_fin["items"]])
        print("Classification facets:", res_fin["facets"]["classifications"])
        print("Department facets:", res_fin["facets"]["departments"])

        # Assertions
        # HR User must see HR and Public, NOT Finance
        hr_doc_names = [d["name"] for d in res_hr["items"]]
        assert "HR_Compensation_2026.pdf" in hr_doc_names, "HR document must be visible to HR user"
        assert "Finance_Quarterly_Pnl.pdf" not in hr_doc_names, "Finance document must NOT be visible to HR user"
        assert res_hr["facets"]["departments"].get("HR", 0) == 1, "HR facet count must be 1"
        assert res_hr["facets"]["departments"].get("Finance", 0) == 0, "HR facet MUST NOT count Finance docs"

        # Finance User must see Finance and Public, NOT HR
        fin_doc_names = [d["name"] for d in res_fin["items"]]
        assert "Finance_Quarterly_Pnl.pdf" in fin_doc_names, "Finance document must be visible to Finance user"
        assert "HR_Compensation_2026.pdf" not in fin_doc_names, "HR document must NOT be visible to Finance user"
        assert res_fin["facets"]["departments"].get("Finance", 0) == 1, "Finance facet count must be 1"
        assert res_fin["facets"]["departments"].get("HR", 0) == 0, "Finance facet MUST NOT count HR docs"

        print("\nSUCCESS: All multi-department search facet assertions passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_facet_test())

