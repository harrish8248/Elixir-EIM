"""Search indexing service for PostgreSQL FTS and Trigram matching."""

import uuid
from typing import Any
from sqlalchemy import text

from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.database import AsyncSessionFactory


async def reindex_search_vectors(tenant_id: str | None = None) -> int:
    """
    Synchronize OCR text and extracted IDP fields into documents table
    and trigger search_vector recalculation.
    """
    async with AsyncSessionFactory() as db:
        # 1. Update ocr_text on documents from document_text
        doc_text_query = """
            UPDATE documents d
            SET ocr_text = dt.extracted_text,
                updated_at = now()
            FROM (
                SELECT document_id, extracted_text
                FROM document_text
                WHERE extracted_text IS NOT NULL
            ) dt
            WHERE d.id = dt.document_id
        """
        if tenant_id:
            doc_text_query += " AND d.tenant_id = :tenant_id"
            await db.execute(text(doc_text_query), {"tenant_id": tenant_id})
        else:
            await db.execute(text(doc_text_query))

        # 2. Update extracted_fields_text on documents from extracted_fields (via capture_jobs)
        fields_query = """
            UPDATE documents d
            SET extracted_fields_text = ef_agg.fields_text,
                updated_at = now()
            FROM (
                SELECT cj.document_id,
                       string_agg(ef.field_name || ': ' || coalesce(ef.field_value, ''), ' ') as fields_text
                FROM capture_jobs cj
                JOIN extracted_fields ef ON ef.job_id = cj.id
                WHERE cj.document_id IS NOT NULL
                GROUP BY cj.document_id
            ) ef_agg
            WHERE d.id = ef_agg.document_id
        """
        if tenant_id:
            fields_query += " AND d.tenant_id = :tenant_id"
            await db.execute(text(fields_query), {"tenant_id": tenant_id})
        else:
            await db.execute(text(fields_query))

        # 3. Touch remaining documents to fire search_vector trigger
        touch_query = "UPDATE documents SET updated_at = now()"
        if tenant_id:
            touch_query += " WHERE tenant_id = :tenant_id"
            res = await db.execute(text(touch_query), {"tenant_id": tenant_id})
        else:
            res = await db.execute(text(touch_query))

        await db.commit()
        count = res.rowcount or 0
        logger.info(f"Reindexed search vectors for {count} documents.")
        return count
