"""Search & Discovery API Router: PostgreSQL FTS with ACL trimming."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.content.models import Document
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.tenancy.database import get_db_session

search_router = APIRouter(prefix="/api/v1/search", tags=["Search & Discovery"])


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
    Full-text search over documents with permission trimming.
    Filters by clearance level inside the SQL query.
    """
    # Clearance-based classification whitelist
    cl_map = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}
    allowed_classifications = [c for c, lvl in cl_map.items() if lvl <= session.clearance_level]

    # Build base query with FTS
    # Use plainto_tsquery for robust user query handling
    stmt = (
        select(
            Document,
            func.ts_rank(Document.search_vector, func.plainto_tsquery("english", q)).label("rank"),
        )
        .where(Document.tenant_id == session.tenant_id)
        .where(Document.is_trashed.is_(False))
        .where(Document.classification.in_(allowed_classifications))
        .where(Document.search_vector.op("@@")(func.plainto_tsquery("english", q)))
    )

    # Additional filters
    if classification:
        stmt = stmt.where(Document.classification == classification.upper())
    if department:
        stmt = stmt.where(Document.department.ilike(f"%{department}%"))
    if status:
        stmt = stmt.where(Document.status == status)

    # Count
    count_stmt = select(func.count()).select_from(
        select(Document)
        .where(Document.tenant_id == session.tenant_id)
        .where(Document.is_trashed.is_(False))
        .where(Document.classification.in_(allowed_classifications))
        .where(Document.search_vector.op("@@")(func.plainto_tsquery("english", q)))
        .subquery()
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # Sort by rank
    stmt = stmt.order_by(text("rank DESC")).offset((page - 1) * page_size).limit(page_size)
    results = (await db.execute(stmt)).all()

    items = []
    for row in results:
        doc = row[0]
        rank = float(row[1]) if row[1] else 0.0

        # Generate snippet from name + description
        snippet_text = doc.name
        if doc.description:
            snippet_text += " — " + doc.description[:200]

        items.append({
            "id": str(doc.id),
            "name": doc.name,
            "description": doc.description,
            "classification": doc.classification,
            "department": doc.department,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
            "status": doc.status,
            "is_record": doc.is_record,
            "tags": doc.tags,
            "workspace_id": str(doc.workspace_id),
            "folder_id": str(doc.folder_id) if doc.folder_id else None,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
            "rank": rank,
            "snippet": snippet_text[:300],
        })

    # Facets: classification counts
    facet_stmt = (
        select(Document.classification, func.count(Document.id).label("count"))
        .where(Document.tenant_id == session.tenant_id)
        .where(Document.is_trashed.is_(False))
        .where(Document.classification.in_(allowed_classifications))
        .where(Document.search_vector.op("@@")(func.plainto_tsquery("english", q)))
        .group_by(Document.classification)
    )
    facets_raw = (await db.execute(facet_stmt)).all()
    facets = {row[0]: row[1] for row in facets_raw}

    return {
        "query": q,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "facets": {"classification": facets},
        "user_clearance": session.clearance_level,
        "allowed_classifications": allowed_classifications,
    }


@search_router.get("/recent", response_model=list[dict])
async def recent_documents(
    limit: int = Query(10, ge=1, le=50),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    """Return most recently updated documents the user has clearance for."""
    cl_map = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}
    allowed_classifications = [c for c, lvl in cl_map.items() if lvl <= session.clearance_level]

    docs = (await db.execute(
        select(Document)
        .where(Document.tenant_id == session.tenant_id)
        .where(Document.is_trashed.is_(False))
        .where(Document.classification.in_(allowed_classifications))
        .order_by(Document.updated_at.desc())
        .limit(limit)
    )).scalars().all()

    return [
        {
            "id": str(d.id),
            "name": d.name,
            "classification": d.classification,
            "mime_type": d.mime_type,
            "status": d.status,
            "updated_at": d.updated_at.isoformat(),
        }
        for d in docs
    ]
