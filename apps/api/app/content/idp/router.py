"""
Intelligent Document Processing (IDP) API Router.
Provides:
- Ingestion with ClamAV scan
- Capture jobs listing & details with extracted fields and line items
- Human validation workbench (accept, correct, reject with audit trail)
- Real-time Capture & IDP metrics dashboard
- Evaluation harness runner
Enforces PEP/PDP on every route and tenant RLS.
"""

import json
from pathlib import Path
import time
from typing import Any
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.service import record_audit_event
from apps.api.app.content.idp.evaluation import EvaluationHarness
from apps.api.app.content.idp.models import ValidateJobRequest
from apps.api.app.content.idp.service import IdpService
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.pep.policy import require_permission
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.database import get_db_session

idp_router = APIRouter(prefix="/api/v1/idp", tags=["Capture & IDP"])
idp_service = IdpService()
harness = EvaluationHarness()


@idp_router.get("/jobs", summary="List capture jobs")
async def list_capture_jobs(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
    _authz=Depends(require_permission("read", "document")),
) -> dict[str, Any]:
    """List capture jobs with optional status filter and pagination."""
    query = """
        SELECT id, tenant_id, document_id, filename, status, document_type,
               classification_confidence, ocr_engine, mean_confidence,
               processing_time_ms, created_at, updated_at
        FROM capture_jobs
        WHERE tenant_id = :tenant_id
    """
    params: dict[str, Any] = {"tenant_id": session.tenant_id, "limit": limit, "offset": offset}
    if status_filter:
        query += " AND status = :status"
        params["status"] = status_filter

    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    jobs = [
        {
            "id": str(r[0]),
            "tenant_id": str(r[1]),
            "document_id": str(r[2]) if r[2] else None,
            "filename": r[3],
            "status": r[4],
            "document_type": r[5],
            "classification_confidence": round(r[6], 2),
            "ocr_engine": r[7],
            "mean_confidence": round(r[8], 2),
            "processing_time_ms": round(r[9], 1),
            "created_at": r[10].isoformat() if r[10] else None,
            "updated_at": r[11].isoformat() if r[11] else None,
        }
        for r in rows
    ]

    count_res = await db.execute(
        text("SELECT count(*) FROM capture_jobs WHERE tenant_id = :tenant_id"),
        {"tenant_id": session.tenant_id},
    )
    total_count = count_res.scalar() or 0

    return {
        "items": jobs,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@idp_router.get("/jobs/{job_id}", summary="Get capture job details")
async def get_capture_job(
    job_id: uuid.UUID,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
    _authz=Depends(require_permission("read", "document")),
) -> dict[str, Any]:
    """Retrieve full details for a capture job including extracted fields and validation checks."""
    job_res = await db.execute(
        text("""
            SELECT id, tenant_id, document_id, filename, status, document_type,
                   classification_confidence, ocr_engine, mean_confidence,
                   processing_time_ms, raw_text, created_at, updated_at
            FROM capture_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """),
        {"job_id": job_id, "tenant_id": session.tenant_id},
    )
    job = job_res.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Capture job not found")

    # Fetch fields
    fields_res = await db.execute(
        text("""
            SELECT field_name, field_value, normalized_value, confidence, page, bbox, extraction_method, is_valid, error_message
            FROM extracted_fields
            WHERE job_id = :job_id AND tenant_id = :tenant_id
        """),
        {"job_id": job_id, "tenant_id": session.tenant_id},
    )
    fields = [
        {
            "field_name": r[0],
            "field_value": r[1],
            "normalized_value": r[2],
            "confidence": round(r[3], 2),
            "page": r[4],
            "bbox": r[5],
            "extraction_method": r[6],
            "is_valid": r[7],
            "error_message": r[8],
        }
        for r in fields_res.fetchall()
    ]

    # Fetch validation results
    val_res = await db.execute(
        text("""
            SELECT rule_name, passed, message, severity, created_at
            FROM validation_results
            WHERE job_id = :job_id AND tenant_id = :tenant_id
        """),
        {"job_id": job_id, "tenant_id": session.tenant_id},
    )
    rules = [
        {
            "rule_name": r[0],
            "passed": r[1],
            "message": r[2],
            "severity": r[3],
        }
        for r in val_res.fetchall()
    ]

    return {
        "id": str(job[0]),
        "tenant_id": str(job[1]),
        "document_id": str(job[2]) if job[2] else None,
        "filename": job[3],
        "status": job[4],
        "document_type": job[5],
        "classification_confidence": round(job[6], 2),
        "ocr_engine": job[7],
        "mean_confidence": round(job[8], 2),
        "processing_time_ms": round(job[9], 1),
        "raw_text": job[10],
        "created_at": job[11].isoformat() if job[11] else None,
        "updated_at": job[12].isoformat() if job[12] else None,
        "fields": fields,
        "validation_results": rules,
    }


@idp_router.post("/jobs/{job_id}/validate", summary="Submit human validation or correction")
async def validate_capture_job(
    job_id: uuid.UUID,
    payload: ValidateJobRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
    _authz=Depends(require_permission("write", "document")),
) -> dict[str, Any]:
    """Human validation workbench action: Accept all, Reject document, or Apply field corrections."""
    job_res = await db.execute(
        text("SELECT id, status, filename FROM capture_jobs WHERE id = :job_id AND tenant_id = :tenant_id"),
        {"job_id": job_id, "tenant_id": session.tenant_id},
    )
    job = job_res.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Capture job not found")

    new_status = "completed"
    if payload.action == "reject":
        new_status = "rejected"
    elif payload.action in ["accept", "correct"]:
        new_status = "completed"

    # Record corrections
    for corr in payload.corrections:
        # Get old value
        f_res = await db.execute(
            text("SELECT field_value, bbox FROM extracted_fields WHERE job_id = :job_id AND field_name = :fname"),
            {"job_id": job_id, "fname": corr.field_name},
        )
        row = f_res.fetchone()
        orig_val = row[0] if row else None
        bbox = row[1] if row else None

        await db.execute(
            text("""
                INSERT INTO field_corrections (id, tenant_id, job_id, field_name, original_value, corrected_value, corrected_by, reason, created_at)
                VALUES (gen_random_uuid(), :tenant_id, :job_id, :field_name, :original_value, :corrected_value, :corrected_by, :reason, now())
            """),
            {
                "tenant_id": session.tenant_id,
                "job_id": job_id,
                "field_name": corr.field_name,
                "original_value": str(orig_val),
                "corrected_value": str(corr.corrected_value),
                "corrected_by": session.user_id,
                "reason": corr.reason,
            },
        )

        # Update field in extracted_fields
        await db.execute(
            text("""
                UPDATE extracted_fields
                SET field_value = :val, is_valid = true, confidence = 1.0
                WHERE job_id = :job_id AND field_name = :fname
            """),
            {"val": str(corr.corrected_value), "job_id": job_id, "fname": corr.field_name},
        )

        # Audit event per correction
        await record_audit_event(
            db=db,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            action="IDP_FIELD_CORRECTED",
            resource_type="capture_job",
            resource_id=str(job_id),
            details={"field": corr.field_name, "old": orig_val, "new": corr.corrected_value, "reason": corr.reason},
        )

    # Update job status
    await db.execute(
        text("UPDATE capture_jobs SET status = :status, updated_at = now() WHERE id = :job_id"),
        {"status": new_status, "job_id": job_id},
    )
    await db.commit()

    await record_audit_event(
        db=db,
        tenant_id=session.tenant_id,
        user_id=session.user_id,
        action=f"IDP_JOB_{payload.action.upper()}",
        resource_type="capture_job",
        resource_id=str(job_id),
        details={"action": payload.action, "comment": payload.comment, "corrections_count": len(payload.corrections)},
    )

    return {"status": "success", "new_job_status": new_status, "corrections_applied": len(payload.corrections)}


@idp_router.get("/stats", summary="Get Capture & IDP Dashboard Statistics")
async def get_idp_stats(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
    _authz=Depends(require_permission("read", "document")),
) -> dict[str, Any]:
    """Return live database analytics for the Capture & IDP Dashboard."""
    # 1. Total processed & status counts
    status_res = await db.execute(
        text("""
            SELECT status, count(*)
            FROM capture_jobs
            WHERE tenant_id = :tenant_id
            GROUP BY status
        """),
        {"tenant_id": session.tenant_id},
    )
    status_counts = dict(status_res.fetchall())
    total_jobs = sum(status_counts.values())

    auto_approved = status_counts.get("auto_approved", 0)
    needs_review = status_counts.get("needs_review", 0)
    completed = status_counts.get("completed", 0)
    rejected = status_counts.get("rejected", 0)

    stp_rate = round((auto_approved / max(total_jobs, 1)) * 100.0, 1) if total_jobs > 0 else 0.0

    # 2. Average confidence and processing time
    avg_res = await db.execute(
        text("""
            SELECT coalesce(avg(mean_confidence), 0.0), coalesce(avg(processing_time_ms), 0.0)
            FROM capture_jobs
            WHERE tenant_id = :tenant_id
        """),
        {"tenant_id": session.tenant_id},
    )
    avg_conf, avg_lat = avg_res.fetchone() or (0.0, 0.0)

    # 3. Accuracy from real corrections
    corr_res = await db.execute(
        text("SELECT count(*) FROM field_corrections WHERE tenant_id = :tenant_id"),
        {"tenant_id": session.tenant_id},
    )
    total_corrections = corr_res.scalar() or 0

    field_res = await db.execute(
        text("SELECT count(*) FROM extracted_fields WHERE tenant_id = :tenant_id"),
        {"tenant_id": session.tenant_id},
    )
    total_fields = field_res.scalar() or 0

    correction_accuracy = (
        round(((total_fields - total_corrections) / max(total_fields, 1)) * 100.0, 1)
        if total_fields > 0
        else 0.0
    )

    has_data = total_jobs > 0

    return {
        "has_data": has_data,
        "total_documents": total_jobs,
        "stp_rate_pct": stp_rate if has_data else 0.0,
        "average_confidence_pct": round(avg_conf, 1) if has_data else 0.0,
        "average_processing_time_ms": round(avg_lat, 1) if has_data else 0.0,
        "review_queue_size": needs_review,
        "auto_approved_count": auto_approved,
        "completed_count": completed,
        "rejected_count": rejected,
        "correction_accuracy_pct": correction_accuracy if total_fields > 0 else 0.0,
        "total_human_corrections": total_corrections,
    }


@idp_router.post("/upload", summary="Ingest document to IDP pipeline")
async def upload_document_to_idp(
    file: UploadFile = File(...),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
    _authz=Depends(require_permission("write", "document")),
) -> dict[str, Any]:
    """Ingest, scan with ClamAV, and process document through OCR and validation pipeline."""
    content = await file.read()
    filename = file.filename or "upload.bin"
    mime_type = file.content_type or "application/octet-stream"

    # ClamAV Antivirus Check
    try:
        from apps.api.app.platform.antivirus import scan_content_with_clamav
        scan_res = await scan_content_with_clamav(content)
        if not scan_res.get("is_clean", True):
            raise HTTPException(status_code=400, detail="Document blocked: Malicious content detected")
    except Exception as e:
        logger.warning(f"ClamAV scan skipped or unavailable: {e}")

    # Process through IDP pipeline
    res = idp_service.process_document(content, filename, mime_type)
    job_id = uuid.uuid4()

    # Persist capture job
    await db.execute(
        text("""
            INSERT INTO capture_jobs (
                id, tenant_id, filename, status, document_type,
                classification_confidence, ocr_engine, mean_confidence,
                processing_time_ms, raw_text, created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, :filename, :status, :document_type,
                :class_conf, :ocr_engine, :mean_conf,
                :proc_time, :raw_text, now(), now()
            )
        """),
        {
            "id": job_id,
            "tenant_id": session.tenant_id,
            "filename": filename,
            "status": res["validation"]["outcome"].lower(),
            "document_type": res["classification"],
            "class_conf": res["classification_confidence"],
            "ocr_engine": res["ocr_engine"],
            "mean_conf": res["mean_confidence"],
            "proc_time": res["latency_ms"],
            "raw_text": res["extracted_text"][:50000],
        },
    )

    # Persist extracted fields
    for fname, fdict in res["fields"].items():
        await db.execute(
            text("""
                INSERT INTO extracted_fields (
                    id, tenant_id, job_id, field_name, field_value,
                    normalized_value, confidence, page, bbox, extraction_method, created_at
                )
                VALUES (
                    gen_random_uuid(), :tenant_id, :job_id, :field_name, :field_value,
                    :normalized_value, :confidence, 1, :bbox, :method, now()
                )
            """),
            {
                "tenant_id": session.tenant_id,
                "job_id": job_id,
                "field_name": fname,
                "field_value": str(fdict.get("normalized_value")),
                "normalized_value": json.dumps(fdict.get("normalized_value")),
                "confidence": fdict.get("confidence", 0.0),
                "bbox": json.dumps(fdict.get("bbox")),
                "method": fdict.get("extraction_method", "heuristic"),
            },
        )

    # Persist validation results
    for rule in res["validation"]["rules"]:
        await db.execute(
            text("""
                INSERT INTO validation_results (
                    id, tenant_id, job_id, rule_name, passed, message, severity, created_at
                )
                VALUES (
                    gen_random_uuid(), :tenant_id, :job_id, :rule_name, :passed, :message, :severity, now()
                )
            """),
            {
                "tenant_id": session.tenant_id,
                "job_id": job_id,
                "rule_name": rule["rule_name"],
                "passed": rule["passed"],
                "message": rule["message"],
                "severity": rule["severity"],
            },
        )

    await db.commit()

    return {
        "job_id": str(job_id),
        "status": res["validation"]["outcome"].lower(),
        "document_type": res["classification"],
        "fields": res["fields"],
        "line_items": res["line_items"],
        "validation": res["validation"],
    }


@idp_router.post("/evaluate", summary="Run benchmark evaluation")
async def evaluate_split(
    split: str = Query("test", pattern="^(train|dev|test)$"),
    session: SessionData = Depends(get_current_session),
    _authz=Depends(require_permission("read", "document")),
) -> dict[str, Any]:
    """Execute IDP evaluation harness on specified split and return metrics report."""
    svc = IdpService()
    svc.learn_from_train_split()
    report = harness.evaluate_pipeline(
        process_fn=svc.process_image_path,
        split_name=split,
        engine_name="tesseract_5.4_idp",
    )
    return report
