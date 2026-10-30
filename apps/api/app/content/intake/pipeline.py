"""Universal File Intake Pipeline and Server-Enforced Guardrails Orchestrator.

Strict sequential execution order:
  1. Size limit enforcement (stream-checked against tenant policy)
  2. True type detection via magic bytes (extension mismatch detection)
  3. Tenant type policy evaluation (ALLOW / QUARANTINE / BLOCK)
  4. Deep archive security inspection (zip bomb, encrypted, member checks)
  5. ClamAV antivirus stream scan (STRICT FAIL-CLOSED: failure/timeout = HTTP 503)
  6. Sandboxed universal text extraction per family
  7. Explainable sensitivity classification (SAFE / SENSITIVE / CRITICAL / UNCLASSIFIED)
  8. Storage of raw object in MinIO under content-hash key
  9. PostgreSQL database persistence (Document, Version, Text, and hash-chained AuditEvent)
"""

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.service import record_audit_event
from apps.api.app.content.intake.archive_inspector import ArchiveInspectionReport, inspect_archive
from apps.api.app.content.intake.classifier import (
    ClassificationReport,
    classify_text,
)
from apps.api.app.content.intake.extractor import ExtractionResult, extract_text_sandboxed
from apps.api.app.content.intake.policy import (
    PolicyEvaluationResult,
    PolicyOutcome,
    TenantGuardrailConfig,
    evaluate_type_policy,
    get_tenant_guardrail_config,
)
from apps.api.app.content.intake.type_detector import TypeDetectionResult, detect_file_type
from apps.api.app.identity.session import SessionData
from apps.api.app.platform.config import settings

logger = logging.getLogger("elixir.intake.pipeline")

# Standard EICAR test string signature
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}"


class ClamAVScanError(HTTPException):
    """Raised when ClamAV daemon is unreachable, times out, or encounters a socket error."""
    def __init__(self, detail: str = "Antivirus scanner unavailable (ClamAV fail-closed enforcement)"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


@dataclass
class IngestionPipelineResult:
    document_id: uuid.UUID | None
    version_id: uuid.UUID | None
    quarantine_id: uuid.UUID | None
    status: str  # allowed, quarantined, blocked, failed
    filename: str
    size_bytes: int
    content_hash: str
    detected_mime: str
    true_extension: str
    family: str
    sensitivity_label: str
    mapped_clearance: str
    classification_reason: str
    masked_findings: list[dict[str, Any]]
    scan_status: str
    scan_details: str
    archive_report: dict[str, Any] | None
    http_status_code: int
    message: str


async def scan_stream_clamav_fail_closed(
    content: bytes,
    host: str = settings.clamav_host,
    port: int = settings.clamav_port,
    timeout_seconds: float = 30.0,
) -> tuple[bool, str]:
    """Scan content bytes with ClamAV via TCP clamd socket with STRICT FAIL-CLOSED enforcement.

    Any socket error, timeout, or unreachable daemon immediately raises ClamAVScanError (HTTP 503).
    There is NO 'scan_unavailable' pass path.
    """
    # 1. Immediate EICAR heuristic check
    if EICAR_SIGNATURE in content[:128]:
        return False, "EICAR-Test-Signature FOUND"

    reader = None
    writer = None
    try:
        # Establish connection with timeout
        connect_coro = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(connect_coro, timeout=5.0)

        # Send zINSTREAM command
        writer.write(b"zINSTREAM\0")
        chunk_size = len(content)
        writer.write(chunk_size.to_bytes(4, byteorder="big"))
        writer.write(content)
        writer.write((0).to_bytes(4, byteorder="big"))
        await writer.drain()

        # Read response
        read_coro = reader.read(1024)
        response_bytes = await asyncio.wait_for(read_coro, timeout=timeout_seconds)

        response = response_bytes.decode("utf-8", errors="replace").strip()
        logger.info(f"ClamAV scan completed with response: '{response}'")

        if "OK" in response and "FOUND" not in response:
            return True, "clean"
        else:
            return False, response
    except TimeoutError:
        logger.error(f"ClamAV scan timed out after {timeout_seconds}s at {host}:{port}")
        raise ClamAVScanError(f"Antivirus scanner timed out after {timeout_seconds}s (ClamAV fail-closed)")
    except (ConnectionRefusedError, OSError) as conn_err:
        logger.error(f"ClamAV daemon connection failed at {host}:{port}: {conn_err}")
        raise ClamAVScanError(f"Antivirus scanner unreachable at {host}:{port} (ClamAV fail-closed)")
    except Exception as exc:
        logger.error(f"ClamAV socket failure: {exc}")
        raise ClamAVScanError(f"Antivirus scanning failed: {exc} (ClamAV fail-closed)")
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def run_universal_intake_pipeline(
    filename: str,
    content: bytes,
    session: SessionData,
    db: AsyncSession,
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    classification_override: str | None = None,
    department: str | None = None,
    description: str | None = None,
) -> IngestionPipelineResult:
    """Execute complete universal file intake pipeline with server-enforced guardrails."""
    size_bytes = len(content)
    content_hash = hashlib.sha256(content).hexdigest()
    tenant_id = session.tenant_id

    # -----------------------------------------------------------------------
    # Step 1: Read Real Persisted Tenant Guardrail Policy from PostgreSQL
    # -----------------------------------------------------------------------
    policy_config: TenantGuardrailConfig = await get_tenant_guardrail_config(tenant_id, db)

    # -----------------------------------------------------------------------
    # Step 2: Magic Bytes True Type Detection & Extension Mismatch Flag
    # -----------------------------------------------------------------------
    detected_type: TypeDetectionResult = detect_file_type(content, filename)

    # -----------------------------------------------------------------------
    # Step 3: Archive Inspection (if archive)
    # -----------------------------------------------------------------------
    archive_report: ArchiveInspectionReport | None = None
    if detected_type.is_archive or "zip" in detected_type.mime_type or "tar" in detected_type.mime_type:
        archive_report = inspect_archive(
            content,
            detected_mime=detected_type.mime_type,
            max_depth=policy_config.archive_max_depth,
            max_members=policy_config.archive_max_members,
            max_ratio=policy_config.archive_max_ratio,
            max_total_bytes=policy_config.max_upload_bytes * 2,
        )

    # -----------------------------------------------------------------------
    # Step 4: Evaluate Tenant Type Policy (ALLOW / QUARANTINE / BLOCK)
    # -----------------------------------------------------------------------
    eval_result: PolicyEvaluationResult = evaluate_type_policy(
        detected=detected_type,
        archive_report=archive_report,
        config=policy_config,
        payload_size=size_bytes,
    )

    # Audit payload base (NEVER include raw document content or text)
    audit_base = {
        "filename": filename,
        "size_bytes": size_bytes,
        "content_hash": content_hash,
        "detected_mime": detected_type.mime_type,
        "rule_matched": eval_result.rule_matched,
    }

    # Handle BLOCK outcome
    if eval_result.outcome == PolicyOutcome.BLOCK:
        await record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_id=str(session.user_id),
            actor_email=session.email,
            action="content:intake:blocked",
            resource_type="document",
            resource_id=content_hash,
            outcome="DENY",
            reason=eval_result.reason,
            payload=audit_base,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=eval_result.reason,
        )

    # Handle QUARANTINE outcome
    if eval_result.outcome == PolicyOutcome.QUARANTINE:
        quarantine_id = uuid.uuid4()
        storage_key = f"quarantine/{tenant_id}/{quarantine_id}/{content_hash}"

        # Write to quarantine_items table in PostgreSQL
        await db.execute(
            text(
                """
                INSERT INTO quarantine_items (
                    id, tenant_id, filename, detected_mime, size_bytes, content_hash,
                    storage_key, reason, status, item_metadata, quarantined_by, created_at
                )
                VALUES (
                    :id, :tenant_id, :filename, :detected_mime, :size_bytes, :content_hash,
                    :storage_key, :reason, 'QUARANTINED', :metadata, :quarantined_by, now()
                )
                """
            ),
            {
                "id": str(quarantine_id),
                "tenant_id": str(tenant_id),
                "filename": filename,
                "detected_mime": detected_type.mime_type,
                "size_bytes": size_bytes,
                "content_hash": content_hash,
                "storage_key": storage_key,
                "reason": eval_result.reason,
                "metadata": json.dumps({
                    "extension_mismatch": detected_type.extension_mismatch,
                    "rule_matched": eval_result.rule_matched,
                }),
                "quarantined_by": session.email,
            },
        )
        await db.commit()

        # Audit quarantine event
        await record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_id=str(session.user_id),
            actor_email=session.email,
            action="content:intake:quarantined",
            resource_type="quarantine_item",
            resource_id=str(quarantine_id),
            outcome="ALLOW",
            reason=f"File quarantined: {eval_result.reason}",
            payload=audit_base,
        )

        return IngestionPipelineResult(
            document_id=None,
            version_id=None,
            quarantine_id=quarantine_id,
            status="quarantined",
            filename=filename,
            size_bytes=size_bytes,
            content_hash=content_hash,
            detected_mime=detected_type.mime_type,
            true_extension=detected_type.extension,
            family=detected_type.family,
            sensitivity_label="UNCLASSIFIED",
            mapped_clearance="RESTRICTED",
            classification_reason=eval_result.reason,
            masked_findings=[],
            scan_status="quarantined_pending_review",
            scan_details="Awaiting administrator review",
            archive_report=None,
            http_status_code=status.HTTP_202_ACCEPTED,
            message=f"File held in quarantine queue: {eval_result.reason}",
        )

    # -----------------------------------------------------------------------
    # Step 5: ClamAV Antivirus Stream Scan (STRICT FAIL-CLOSED)
    # -----------------------------------------------------------------------
    is_clean = False
    scan_detail = ""
    try:
        is_clean, scan_detail = await scan_stream_clamav_fail_closed(content)
    except ClamAVScanError as scan_err:
        # ClamAV daemon down / error / timeout: Record audit event and propagate HTTP 503
        await record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_id=str(session.user_id),
            actor_email=session.email,
            action="content:antivirus:scanner_offline",
            resource_type="document",
            resource_id=content_hash,
            outcome="DENY",
            reason="ClamAV daemon offline or timed out; ingestion blocked per fail-closed policy",
            payload=audit_base,
        )
        raise

    if not is_clean:
        # Malware or virus found
        await record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_id=str(session.user_id),
            actor_email=session.email,
            action="content:antivirus:malware_detected",
            resource_type="document",
            resource_id=content_hash,
            outcome="DENY",
            reason=f"ClamAV malware signature detected: {scan_detail}",
            payload={**audit_base, "virus_signature": scan_detail},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malware or malicious signature detected: {scan_detail}",
        )

    # -----------------------------------------------------------------------
    # Step 6: Sandboxed Universal Text Extraction per Family
    # -----------------------------------------------------------------------
    extraction: ExtractionResult = await extract_text_sandboxed(
        data=content,
        mime_type=detected_type.mime_type,
        family=detected_type.family,
        timeout_seconds=10.0,
    )

    # -----------------------------------------------------------------------
    # Step 7: Explainable Sensitivity Classification
    # -----------------------------------------------------------------------
    classification: ClassificationReport = classify_text(extraction.text)

    # Resolve security clearance
    final_clearance = classification_override or classification.mapped_clearance
    effective_department = department or session.department

    # -----------------------------------------------------------------------
    # Step 8: MinIO Content-Hash Storage
    # -----------------------------------------------------------------------
    storage_key = f"documents/{tenant_id}/{content_hash[:2]}/{content_hash}"
    from apps.api.app.content.router import upload_to_minio
    await upload_to_minio(settings.s3_bucket_name, storage_key, content, detected_type.mime_type)

    # -----------------------------------------------------------------------
    # Step 9: PostgreSQL Document Persistence & Hash-Chained Audit Ledger
    # -----------------------------------------------------------------------
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()

    # Masked findings JSON
    masked_findings = [
        {
            "detector": f.detector,
            "category": f.category,
            "count": f.count,
            "masked_examples": f.masked_examples,
        }
        for f in classification.findings
    ]

    archive_meta = None
    if archive_report:
        archive_meta = {
            "member_count": archive_report.member_count,
            "compression_ratio": archive_report.compression_ratio,
            "max_depth": archive_report.max_depth,
            "is_encrypted": archive_report.is_encrypted,
        }

    # 1. Insert Document
    await db.execute(
        text(
            """
            INSERT INTO documents (
                id, tenant_id, workspace_id, folder_id, name, description,
                classification, department, mime_type, file_extension,
                size_bytes, content_hash, storage_key, status, is_record,
                is_trashed, tags, metadata, version_count, current_version_id,
                created_by_id, created_at, updated_at,
                true_mime_type, extension_mismatch, sensitivity_label,
                classification_reason, archive_inspection, scan_status, scan_details,
                ocr_text
            )
            VALUES (
                :id, :tenant_id, :workspace_id, :folder_id, :name, :description,
                :classification, :department, :mime_type, :file_extension,
                :size_bytes, :content_hash, :storage_key, 'ready', false,
                false, '[]'::jsonb, :metadata, 1, :current_version_id,
                :created_by_id, now(), now(),
                :true_mime_type, :extension_mismatch, :sensitivity_label,
                :classification_reason, :archive_inspection, 'clean', 'ClamAV stream scan verified clean',
                :ocr_text
            )
            """
        ),
        {
            "id": str(document_id),
            "tenant_id": str(tenant_id),
            "workspace_id": str(workspace_id),
            "folder_id": str(folder_id) if folder_id else None,
            "name": filename,
            "description": description or classification.summary_reason,
            "classification": final_clearance,
            "department": effective_department,
            "mime_type": detected_type.mime_type,
            "file_extension": detected_type.extension,
            "size_bytes": size_bytes,
            "content_hash": content_hash,
            "storage_key": storage_key,
            "metadata": json.dumps({"intake_pipeline": "universal_v1", "parser": extraction.parser_used}),
            "current_version_id": str(version_id),
            "created_by_id": str(session.user_id),
            "true_mime_type": detected_type.mime_type,
            "extension_mismatch": detected_type.extension_mismatch,
            "sensitivity_label": classification.label.value,
            "classification_reason": json.dumps({
                "summary": classification.summary_reason,
                "confidence": classification.confidence,
                "findings": masked_findings,
            }),
            "archive_inspection": json.dumps(archive_meta) if archive_meta else None,
            "ocr_text": extraction.text[:20000] if extraction.text else None,
        },
    )

    # 2. Insert DocumentVersion
    await db.execute(
        text(
            """
            INSERT INTO document_versions (
                id, tenant_id, document_id, version_number, name, mime_type,
                size_bytes, content_hash, storage_key, status, scan_result,
                ocr_status, comment, created_by_id, created_at
            )
            VALUES (
                :id, :tenant_id, :document_id, 1, :name, :mime_type,
                :size_bytes, :content_hash, :storage_key, 'ready', 'clean',
                :ocr_status, 'Initial ingestion via Universal Intake Pipeline',
                :created_by_id, now()
            )
            """
        ),
        {
            "id": str(version_id),
            "tenant_id": str(tenant_id),
            "document_id": str(document_id),
            "name": filename,
            "mime_type": detected_type.mime_type,
            "size_bytes": size_bytes,
            "content_hash": content_hash,
            "storage_key": storage_key,
            "ocr_status": "completed" if extraction.has_text else "not_applicable",
            "created_by_id": str(session.user_id),
        },
    )

    # 3. Insert DocumentText (for search indexing)
    if extraction.text:
        await db.execute(
            text(
                """
                INSERT INTO document_text (id, tenant_id, document_id, version_id, extracted_text, created_at)
                VALUES (gen_random_uuid(), :tenant_id, :document_id, :version_id, :text, now())
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "version_id": str(version_id),
                "text": extraction.text,
            },
        )

    await db.commit()

    # 4. Hash-chained Audit Ledger Event (WITHOUT document text)
    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=str(session.user_id),
        actor_email=session.email,
        action="content:document:ingested",
        resource_type="document",
        resource_id=str(document_id),
        outcome="ALLOW",
        reason=f"Universal intake passed: ClamAV clean, sensitivity {classification.label.value} ({classification.mapped_clearance})",
        payload={
            **audit_base,
            "document_id": str(document_id),
            "sensitivity_label": classification.label.value,
            "mapped_clearance": final_clearance,
            "findings_count": classification.total_detections,
            "has_text": extraction.has_text,
            "character_count": extraction.character_count,
        },
    )

    return IngestionPipelineResult(
        document_id=document_id,
        version_id=version_id,
        quarantine_id=None,
        status="allowed",
        filename=filename,
        size_bytes=size_bytes,
        content_hash=content_hash,
        detected_mime=detected_type.mime_type,
        true_extension=detected_type.extension,
        family=detected_type.family,
        sensitivity_label=classification.label.value,
        mapped_clearance=final_clearance,
        classification_reason=classification.summary_reason,
        masked_findings=masked_findings,
        scan_status="clean",
        scan_details="Clean ClamAV stream scan verified",
        archive_report=archive_meta,
        http_status_code=status.HTTP_201_CREATED,
        message="Document verified, antivirus scanned, and stored successfully.",
    )
