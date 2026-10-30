"""Search & Discovery API Router: PostgreSQL FTS, pg_trgm fuzzy matching, and in-SQL ACL trimming."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.pep.policy import require_permission
from apps.api.app.search.service import reindex_search_vectors
from apps.api.app.tenancy.database import get_db_session

search_router = APIRouter(prefix="/api/v1/search", tags=["Search & Discovery"])


async def get_search_db(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> AsyncSession:
    """Ensure PostgreSQL session-local tenant_id is always set for RLS enforcement."""
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(session.tenant_id)},
    )
    return db


CLASSIFICATION_LEVELS = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}


@search_router.get("", response_model=dict[str, Any])
async def search(
    q: str | None = Query(None, description="Search query string"),
    classification: str | None = None,
    department: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_search_db),
    _authz=Depends(require_permission("content:read", "document")),
) -> dict[str, Any]:
    """
    Enhanced full-text and fuzzy search across document metadata, OCR text, and extracted IDP fields.
    When query is empty, provides browse mode with recent documents and real permission-trimmed facets.
    Applies in-SQL department and clearance trimming for zero-leak multi-tenancy.
    """
    user_clearance = getattr(session, "clearance_level", 2)
    user_dept = getattr(session, "department", None)
    user_roles = getattr(session, "roles", [])

    allowed_classifications = [
        cls_name
        for cls_name, lvl in CLASSIFICATION_LEVELS.items()
        if lvl <= user_clearance
    ]

    is_privileged = any(
        r in user_roles for r in ["Admin", "SuperAdmin", "Auditor", "RecordsManager", "GlobalAdmin"]
    )

    query_str = (q or "").strip()
    where_clauses = [
        "d.tenant_id = :tenant_id",
        "d.is_trashed = false",
        "d.classification = ANY(:allowed_classifications)",
    ]
    params: dict[str, Any] = {
        "tenant_id": session.tenant_id,
        "allowed_classifications": allowed_classifications,
    }

    if query_str:
        params["query"] = query_str
        params["query_like"] = f"%{query_str}%"

    # Department ACL: non-privileged users cannot view other departments' documents unless public/unassigned
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

    # Combined hybrid search: websearch_to_tsquery (simple + english) + pg_trgm fuzzy + ILIKE
    if query_str:
        where_clauses.append(
            "("
            "d.search_vector @@ websearch_to_tsquery('simple', :query) "
            "OR d.search_vector @@ websearch_to_tsquery('english', :query) "
            "OR d.search_vector @@ plainto_tsquery('simple', :query) "
            "OR d.search_vector @@ plainto_tsquery('english', :query) "
            "OR d.name ILIKE :query_like "
            "OR d.description ILIKE :query_like "
            "OR coalesce(d.extracted_fields_text, '') ILIKE :query_like "
            "OR coalesce(d.ocr_text, '') ILIKE :query_like "
            "OR word_similarity(:query, d.name) > 0.3 "
            "OR word_similarity(:query, coalesce(d.extracted_fields_text, '')) > 0.3 "
            "OR word_similarity(:query, coalesce(d.ocr_text, '')) > 0.3 "
            "OR similarity(d.name, :query) > 0.25 "
            "OR EXISTS (SELECT 1 FROM document_text dt WHERE dt.document_id = d.id AND dt.extracted_text ILIKE :query_like)"
            ")"
        )

    where_sql = " AND ".join(where_clauses)

    # 1. Total count query
    count_sql = f"SELECT count(*) FROM documents d WHERE {where_sql}"
    total = (await db.execute(text(count_sql), params)).scalar() or 0

    # 2. Main results query with rank and highlighted snippet
    page_num = int(page.default if hasattr(page, "default") else page)
    page_sz = int(page_size.default if hasattr(page_size, "default") else page_size)
    offset = (page_num - 1) * page_sz
    params["limit"] = page_sz
    params["offset"] = offset

    if query_str:
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
                COALESCE(
                    ts_rank(d.search_vector, websearch_to_tsquery('simple', :query)) * 2.5 +
                    ts_rank(d.search_vector, websearch_to_tsquery('english', :query)) * 1.5 +
                    word_similarity(:query, d.name) * 2.0 +
                    word_similarity(:query, coalesce(d.extracted_fields_text, '')) * 1.5,
                    0.0
                ) as rank,
                COALESCE(
                    NULLIF(ts_headline('english', coalesce(d.ocr_text, d.description, d.name), plainto_tsquery('english', :query), 'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15'), ''),
                    NULLIF(ts_headline('simple', coalesce(d.extracted_fields_text, d.name), plainto_tsquery('simple', :query), 'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15'), ''),
                    d.description,
                    d.name
                ) as snippet
            FROM documents d
            WHERE {where_sql}
            ORDER BY rank DESC, d.updated_at DESC
            LIMIT :limit OFFSET :offset
        """
    else:
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
                1.0 as rank,
                COALESCE(d.description, d.name) as snippet
            FROM documents d
            WHERE {where_sql}
            ORDER BY d.updated_at DESC
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
            "rank": round(float(r["rank"]), 4) if r["rank"] else 0.0,
            "snippet": snippet_text[:350],
        })

    # 3. Facets query: counts grouped by classification and department with same permission filters
    facet_sql = f"""
        SELECT d.classification, count(*) as count
        FROM documents d
        WHERE {where_sql}
        GROUP BY d.classification
    """
    facet_rows = (await db.execute(text(facet_sql), params)).all()
    facets_cls = {row[0]: row[1] for row in facet_rows}

    dept_facet_sql = f"""
        SELECT COALESCE(d.department, 'Unassigned') as dept, count(*) as count
        FROM documents d
        WHERE {where_sql}
        GROUP BY d.department
    """
    dept_rows = (await db.execute(text(dept_facet_sql), params)).all()
    facets_dept = {row[0]: row[1] for row in dept_rows}

    return {
        "query": q,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "facets": {
            "classifications": facets_cls,
            "departments": facets_dept,
            "classification": facets_cls,
            "department": facets_dept,
        },
        "user_clearance": user_clearance,
        "user_department": user_dept,
        "allowed_classifications": allowed_classifications,
    }


@search_router.get("/popular-queries", response_model=list[str])
async def popular_queries(
    limit: int = Query(6, ge=1, le=12),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_search_db),
    _authz=Depends(require_permission("content:read", "document")),
) -> list[str]:
    """Retrieve top vendors and frequent document terms accessible to the current user."""
    user_clearance = getattr(session, "clearance_level", 2)
    user_dept = getattr(session, "department", None)
    user_roles = getattr(session, "roles", [])

    allowed_classifications = [
        cls_name
        for cls_name, lvl in CLASSIFICATION_LEVELS.items()
        if lvl <= user_clearance
    ]
    is_privileged = any(
        r in user_roles for r in ["Admin", "SuperAdmin", "Auditor", "RecordsManager", "GlobalAdmin"]
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
        SELECT term FROM (
            SELECT DISTINCT split_part(name, '.', 1) as term
            FROM documents
            WHERE {where_sql} AND length(name) BETWEEN 3 AND 30
            UNION
            SELECT DISTINCT name as term
            FROM vendors
            WHERE tenant_id = :tenant_id
        ) sub
        WHERE length(term) >= 3
        LIMIT :limit
    """
    rows = (await db.execute(text(query_sql), params)).scalars().all()
    return list(rows)


@search_router.get("/autocomplete", response_model=list[str])
async def autocomplete(
    q: str = Query(..., min_length=1, description="Query prefix for suggestions"),
    limit: int = Query(8, ge=1, le=20),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_search_db),
    _authz=Depends(require_permission("content:read", "document")),
) -> list[str]:
    """Provide real-time autocomplete suggestions matching document names and tags within tenant ACL."""
    user_clearance = getattr(session, "clearance_level", 2)
    user_dept = getattr(session, "department", None)
    user_roles = getattr(session, "roles", [])

    allowed_classifications = [
        cls_name
        for cls_name, lvl in CLASSIFICATION_LEVELS.items()
        if lvl <= user_clearance
    ]
    is_privileged = any(
        r in user_roles for r in ["Admin", "SuperAdmin", "Auditor", "RecordsManager", "GlobalAdmin"]
    )

    where_clauses = [
        "tenant_id = :tenant_id",
        "is_trashed = false",
        "classification = ANY(:allowed_classifications)",
        "(name ILIKE :prefix OR similarity(name, :q) > 0.3)",
    ]
    params: dict[str, Any] = {
        "tenant_id": session.tenant_id,
        "allowed_classifications": allowed_classifications,
        "prefix": f"{q.strip()}%",
        "q": q.strip(),
        "limit": limit,
    }

    if not is_privileged and user_dept:
        where_clauses.append("(department = :user_dept OR department IS NULL OR classification = 'PUBLIC')")
        params["user_dept"] = user_dept

    where_sql = " AND ".join(where_clauses)
    query_sql = f"""
        SELECT name FROM documents
        WHERE {where_sql}
        ORDER BY similarity(name, :q) DESC, name ASC
        LIMIT :limit
    """
    rows = (await db.execute(text(query_sql), params)).scalars().all()
    return list(dict.fromkeys(rows))


@search_router.get("/recent", response_model=list[dict[str, Any]])
async def recent_documents(
    limit: int = Query(10, ge=1, le=50),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_search_db),
    _authz=Depends(require_permission("content:read", "document")),
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
        r in user_roles for r in ["Admin", "SuperAdmin", "Auditor", "RecordsManager", "GlobalAdmin"]
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


@search_router.post("/reindex", response_model=dict[str, Any])
async def reindex_documents(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_search_db),
    _authz=Depends(require_permission("content:write", "document")),
) -> dict[str, Any]:
    """Rebuild search index vectors from document OCR text and extracted IDP fields."""
    count = await reindex_search_vectors(str(session.tenant_id))
    return {"status": "success", "reindexed_count": count}
