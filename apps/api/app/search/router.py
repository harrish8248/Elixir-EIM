"""Search & Discovery API Router: PostgreSQL FTS with in-SQL ACL and department trimming."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.tenancy.database import get_db_session

search_router = APIRouter(prefix="/api/v1/search", tags=["Search & Discovery"])

CLASSIFICATION_LEVELS = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}


@search_router.get("", response_model=dict[str, Any])
async def search(
    q: str = Query(..., description="Search query string"),
    classification: str | None = None,
    department: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    PostgreSQL full-text search with strict in-SQL permission trimming:
    1. Tenant boundary: tenant_id = :tenant_id
    2. Clearance vs Classification: classification level <= user clearance_level
    3. Department segregation: if user is not Admin/Auditor/RecordsManager,
       they can only view documents in their own department OR unassigned/public documents.
    4. Text search over tsvector column covering name, metadata, and OCR text, with ILIKE fallback.
    5. Returns matching items, highlighted snippets, rank, counts, and classification facets.
    """
    user_clearance = getattr(session, "clearance_level", 2)
    user_dept = getattr(session, "department", None)
    user_roles = getattr(session, "roles", [])

    # Clearance allowed list
    allowed_classifications = [
        cls_name
        for cls_name, lvl in CLASSIFICATION_LEVELS.items()
        if lvl <= user_clearance
    ]

    is_privileged = any(
        r in user_roles for r in ["Admin", "SuperAdmin", "Auditor", "RecordsManager"]
    )

    # Base WHERE clauses inside SQL
    where_clauses = [
        "d.tenant_id = :tenant_id",
        "d.is_trashed = false",
        "d.classification = ANY(:allowed_classifications)",
    ]
    params: dict[str, Any] = {
        "tenant_id": session.tenant_id,
        "allowed_classifications": allowed_classifications,
        "query": q,
    }

    # Department segregation: Non-privileged users only see their own department or unassigned
    if not is_privileged and user_dept:
        where_clauses.append("(d.department = :user_dept OR d.department IS NULL OR d.classification = 'PUBLIC')")
        params["user_dept"] = user_dept

    # Optional filter params
    if classification:
        where_clauses.append("d.classification = :classification")
        params["classification"] = classification.upper()
    if department:
        where_clauses.append("d.department ILIKE :filter_dept")
        params["filter_dept"] = f"%{department}%"
    if status:
        where_clauses.append("d.status = :status")
        params["status"] = status

    # Text search condition (search_vector match OR name/description/metadata ILIKE)
    where_clauses.append(
        "(d.search_vector @@ plainto_tsquery('english', :query) "
        "OR d.name ILIKE :query_like "
        "OR d.description ILIKE :query_like "
        "OR EXISTS (SELECT 1 FROM document_text dt WHERE dt.document_id = d.id AND dt.extracted_text ILIKE :query_like))"
    )
    params["query_like"] = f"%{q}%"

    where_sql = " AND ".join(where_clauses)

    # 1. Total count query
    count_sql = f"SELECT count(*) FROM documents d WHERE {where_sql}"
    total = (await db.execute(text(count_sql), params)).scalar() or 0

    # 2. Main results query with rank and snippet
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = f"""
        SELECT
            d.id,
            d.name,
            d.description,
            d.classification,
            d.department,
            d.mime_type,
            d.size_bytes,
            d.status,
            d.is_record,
            d.tags,
            d.workspace_id,
            d.folder_id,
            d.created_at,
            d.updated_at,
            COALESCE(ts_rank(d.search_vector, plainto_tsquery('english', :query)), 0.0) as rank,
            COALESCE(
                (SELECT substring(dt.extracted_text from 1 for 200) FROM document_text dt WHERE dt.document_id = d.id LIMIT 1),
                d.description,
                d.name
            ) as snippet
        FROM documents d
        WHERE {where_sql}
        ORDER BY rank DESC, d.updated_at DESC
        LIMIT :limit OFFSET :offset
    """
    rows = (await db.execute(text(data_sql), params)).mappings().all()

    items = []
    for r in rows:
        snippet_text = r["snippet"] or r["name"]
        items.append({
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"],
            "classification": r["classification"],
            "department": r["department"],
            "mime_type": r["mime_type"],
            "size_bytes": r["size_bytes"],
            "status": r["status"],
            "is_record": r["is_record"],
            "tags": r["tags"] or [],
            "workspace_id": str(r["workspace_id"]),
            "folder_id": str(r["folder_id"]) if r["folder_id"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else "",
            "rank": float(r["rank"]) if r["rank"] else 0.0,
            "snippet": snippet_text[:300],
        })

    # 3. Facets query: counts grouped by classification with same permission filters
    facet_sql = f"""
        SELECT d.classification, count(*) as count
        FROM documents d
        WHERE {where_sql}
        GROUP BY d.classification
    """
    facet_rows = (await db.execute(text(facet_sql), params)).all()
    facets = {row[0]: row[1] for row in facet_rows}

    return {
        "query": q,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "facets": {"classification": facets},
        "user_clearance": user_clearance,
        "user_department": user_dept,
        "allowed_classifications": allowed_classifications,
    }


@search_router.get("/recent", response_model=list[dict[str, Any]])
async def recent_documents(
    limit: int = Query(10, ge=1, le=50),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Return most recently updated documents the user has clearance and department access for."""
    user_clearance = getattr(session, "clearance_level", 2)
    user_dept = getattr(session, "department", None)
    user_roles = getattr(session, "roles", [])

    allowed_classifications = [
        cls_name
        for cls_name, lvl in CLASSIFICATION_LEVELS.items()
        if lvl <= user_clearance
    ]
    is_privileged = any(
        r in user_roles for r in ["Admin", "SuperAdmin", "Auditor", "RecordsManager"]
    )

    where_clauses = [
        "tenant_id = :tenant_id",
        "is_trashed = false",
        "classification = ANY(:allowed_classifications)",
    ]
    params: dict[str, Any] = {
        "tenant_id": session.tenant_id,
        "allowed_classifications": allowed_classifications,
        "limit": limit,
    }
    if not is_privileged and user_dept:
        where_clauses.append("(department = :user_dept OR department IS NULL OR classification = 'PUBLIC')")
        params["user_dept"] = user_dept

    where_sql = " AND ".join(where_clauses)
    query_sql = f"""
        SELECT id, name, classification, mime_type, status, updated_at
        FROM documents
        WHERE {where_sql}
        ORDER BY updated_at DESC
        LIMIT :limit
    """
    rows = (await db.execute(text(query_sql), params)).mappings().all()

    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "classification": r["classification"],
            "mime_type": r["mime_type"],
            "status": r["status"],
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else "",
        }
        for r in rows
    ]
