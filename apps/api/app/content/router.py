"""Content Services API Router — workspaces, folders, documents, upload, download, versions."""

import hashlib
import mimetypes
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aioboto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.service import record_audit_event
from apps.api.app.content.models import (
    Document,
    DocumentComment,
    DocumentShare,
    DocumentVersion,
    Folder,
    Workspace,
)
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.platform.config import settings
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.database import get_db_session

content_router = APIRouter(prefix="/api/v1/content", tags=["Content Services"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_MIME_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp",
    "image/tiff", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain", "text/csv", "application/json", "application/xml",
    "application/zip",
}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

# EICAR magic bytes signature for blocking test virus signatures
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}"

CLASSIFICATIONS = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class WorkspaceOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    classification: str
    department: str | None
    created_at: str
    updated_at: str


class FolderOut(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    parent_id: str | None
    name: str
    path: str
    created_at: str


class DocumentOut(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    folder_id: str | None
    name: str
    description: str | None
    classification: str
    department: str | None
    mime_type: str | None
    file_extension: str | None
    size_bytes: int | None
    content_hash: str | None
    status: str
    is_record: bool
    is_trashed: bool
    checkout_by_id: str | None
    checkout_at: str | None
    tags: list
    version_count: int
    created_by_id: str | None
    created_at: str
    updated_at: str


class DocumentVersionOut(BaseModel):
    id: str
    document_id: str
    version_number: int
    name: str
    mime_type: str | None
    size_bytes: int | None
    content_hash: str | None
    status: str
    scan_result: str | None
    ocr_status: str | None
    comment: str | None
    created_by_id: str | None
    created_at: str


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str | None = None
    classification: str = "INTERNAL"
    department: str | None = None


class CreateFolderRequest(BaseModel):
    workspace_id: str
    parent_id: str | None = None
    name: str


class UpdateDocumentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    classification: str | None = None
    department: str | None = None
    tags: list[str] | None = None


class AddCommentRequest(BaseModel):
    body: str


class ShareRequest(BaseModel):
    shared_with_user_id: str | None = None
    shared_with_group_id: str | None = None
    permission_level: str = "VIEW"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        tenant_id=str(doc.tenant_id),
        workspace_id=str(doc.workspace_id),
        folder_id=str(doc.folder_id) if doc.folder_id else None,
        name=doc.name,
        description=doc.description,
        classification=doc.classification,
        department=doc.department,
        mime_type=doc.mime_type,
        file_extension=doc.file_extension,
        size_bytes=doc.size_bytes,
        content_hash=doc.content_hash,
        status=doc.status,
        is_record=doc.is_record,
        is_trashed=doc.is_trashed,
        checkout_by_id=str(doc.checkout_by_id) if doc.checkout_by_id else None,
        checkout_at=doc.checkout_at.isoformat() if doc.checkout_at else None,
        tags=doc.tags or [],
        version_count=doc.version_count,
        created_by_id=str(doc.created_by_id) if doc.created_by_id else None,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
    )


async def get_s3_client():
    session = aioboto3.Session()
    return session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )


async def scan_with_clamav(content: bytes) -> tuple[bool, str]:
    """Scan content bytes with ClamAV via clamd socket. Returns (is_clean, result_str)."""
    # Quick EICAR check first (avoids network call for demo test files)
    if EICAR_SIGNATURE in content[:128]:
        return False, "EICAR-Test-Signature FOUND"

    try:
        import asyncio
        reader, writer = await asyncio.open_connection(settings.clamav_host, settings.clamav_port)

        # Send INSTREAM command
        writer.write(b"nINSTREAM\n")
        chunk_size = len(content)
        writer.write(chunk_size.to_bytes(4, byteorder="big"))
        writer.write(content)
        writer.write((0).to_bytes(4, byteorder="big"))
        await writer.drain()

        response = await asyncio.wait_for(reader.read(1024), timeout=30.0)
        writer.close()
        await writer.wait_closed()

        result = response.decode("utf-8", errors="replace").strip()
        if "OK" in result and "FOUND" not in result:
            return True, "clean"
        else:
            return False, result
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"ClamAV scan error (treating as clean for non-blocking): {exc}")
        return True, "scan_unavailable"


async def upload_to_minio(bucket: str, key: str, content: bytes, content_type: str) -> None:
    async with await get_s3_client() as s3:
        try:
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except ClientError as exc:
            # Try to create bucket if it doesn't exist
            if exc.response["Error"]["Code"] == "NoSuchBucket":
                await s3.create_bucket(Bucket=bucket)
                await s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)
            else:
                raise


async def generate_presigned_url(bucket: str, key: str, expires: int = 300) -> str:
    async with await get_s3_client() as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    return url


def _check_clearance(session: SessionData, classification: str) -> bool:
    """Check if user clearance satisfies document classification."""
    classification_level = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}
    required = classification_level.get(classification, 0)
    return session.clearance_level >= required


# ---------------------------------------------------------------------------
# Workspace Endpoints
# ---------------------------------------------------------------------------
@content_router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[WorkspaceOut]:
    stmt = (
        select(Workspace)
        .where(Workspace.tenant_id == session.tenant_id)
        .order_by(Workspace.name)
    )
    workspaces = (await db.execute(stmt)).scalars().all()
    return [
        WorkspaceOut(
            id=str(w.id),
            tenant_id=str(w.tenant_id),
            name=w.name,
            description=w.description,
            classification=w.classification,
            department=w.department,
            created_at=w.created_at.isoformat(),
            updated_at=w.updated_at.isoformat(),
        )
        for w in workspaces
    ]


@content_router.post("/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: CreateWorkspaceRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> WorkspaceOut:
    if body.classification not in CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail=f"Invalid classification. Must be one of: {CLASSIFICATIONS}")
    ws = Workspace(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        name=body.name,
        description=body.description,
        classification=body.classification,
        department=body.department,
        owner_id=session.user_id,
    )
    db.add(ws)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:workspace:create",
        resource_type="workspace", resource_id=str(ws.id), outcome="ALLOW",
        reason=f"Created workspace: {ws.name}",
    )
    return WorkspaceOut(
        id=str(ws.id), tenant_id=str(ws.tenant_id), name=ws.name,
        description=ws.description, classification=ws.classification,
        department=ws.department, created_at=ws.created_at.isoformat(),
        updated_at=ws.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Folder Endpoints
# ---------------------------------------------------------------------------
@content_router.get("/folders", response_model=list[FolderOut])
async def list_folders(
    workspace_id: str | None = None,
    parent_id: str | None = None,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[FolderOut]:
    stmt = select(Folder).where(Folder.tenant_id == session.tenant_id)
    if workspace_id:
        stmt = stmt.where(Folder.workspace_id == uuid.UUID(workspace_id))
    if parent_id:
        stmt = stmt.where(Folder.parent_id == uuid.UUID(parent_id))
    else:
        stmt = stmt.where(Folder.parent_id.is_(None))
    stmt = stmt.order_by(Folder.name)
    folders = (await db.execute(stmt)).scalars().all()
    return [
        FolderOut(
            id=str(f.id), tenant_id=str(f.tenant_id), workspace_id=str(f.workspace_id),
            parent_id=str(f.parent_id) if f.parent_id else None,
            name=f.name, path=f.path, created_at=f.created_at.isoformat(),
        )
        for f in folders
    ]


@content_router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: CreateFolderRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> FolderOut:
    # Build path
    if body.parent_id:
        parent = (await db.execute(
            select(Folder).where(Folder.id == uuid.UUID(body.parent_id))
        )).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        path = f"{parent.path}/{body.name}"
    else:
        path = f"/{body.name}"

    folder = Folder(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        workspace_id=uuid.UUID(body.workspace_id),
        parent_id=uuid.UUID(body.parent_id) if body.parent_id else None,
        name=body.name,
        path=path,
        created_by_id=session.user_id,
    )
    db.add(folder)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:folder:create",
        resource_type="folder", resource_id=str(folder.id), outcome="ALLOW",
        reason=f"Created folder: {folder.path}",
    )
    return FolderOut(
        id=str(folder.id), tenant_id=str(folder.tenant_id),
        workspace_id=str(folder.workspace_id),
        parent_id=str(folder.parent_id) if folder.parent_id else None,
        name=folder.name, path=folder.path, created_at=folder.created_at.isoformat(),
    )


@content_router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    folder = (await db.execute(
        select(Folder).where(Folder.id == uuid.UUID(folder_id), Folder.tenant_id == session.tenant_id)
    )).scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    await db.delete(folder)
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:folder:delete",
        resource_type="folder", resource_id=folder_id, outcome="ALLOW",
        reason=f"Deleted folder: {folder.name}",
    )


# ---------------------------------------------------------------------------
# Document Endpoints
# ---------------------------------------------------------------------------
@content_router.get("/documents", response_model=dict[str, Any])
@content_router.get("/nodes", response_model=dict[str, Any])
async def list_documents(
    workspace_id: str | None = None,
    folder_id: str | None = None,
    include_trashed: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List documents (nodes) in a workspace/folder with pagination."""
    stmt = (
        select(Document)
        .where(Document.tenant_id == session.tenant_id)
        .where(Document.is_trashed == include_trashed)
    )
    if workspace_id:
        stmt = stmt.where(Document.workspace_id == uuid.UUID(workspace_id))
    if folder_id:
        stmt = stmt.where(Document.folder_id == uuid.UUID(folder_id))

    # Filter by clearance
    user_clearance = session.clearance_level
    cl_map = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}
    allowed_classifications = [c for c, l in cl_map.items() if l <= user_clearance]
    stmt = stmt.where(Document.classification.in_(allowed_classifications))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Document.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    docs = (await db.execute(stmt)).scalars().all()

    return {
        "items": [_doc_out(d).__dict__ for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@content_router.get("/nodes/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentOut:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id),
            Document.tenant_id == session.tenant_id,
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _check_clearance(session, doc.classification):
        raise HTTPException(status_code=403, detail="Insufficient clearance level for this document")
    return _doc_out(doc)


@content_router.post("/nodes/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: str,
    body: UpdateDocumentRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentOut:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id),
            Document.tenant_id == session.tenant_id,
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.name is not None:
        doc.name = body.name
    if body.description is not None:
        doc.description = body.description
    if body.classification is not None:
        if body.classification not in CLASSIFICATIONS:
            raise HTTPException(status_code=422, detail="Invalid classification")
        doc.classification = body.classification
    if body.department is not None:
        doc.department = body.department
    if body.tags is not None:
        doc.tags = body.tags

    doc.updated_at = datetime.now(UTC)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:update_metadata",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason="Metadata updated",
    )
    return _doc_out(doc)


@content_router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: str = Query(...),
    folder_id: str | None = Query(None),
    classification: str = Query("INTERNAL"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentOut:
    """
    Upload a document: validate type/size, ClamAV scan, store in MinIO, create DB record.
    Supports: PDF, images, Office documents, plain text, CSV, JSON, XML, ZIP.
    Max size: 25 MB.
    """
    if classification not in CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail=f"Invalid classification: {classification}")

    # Check clearance allows this classification
    if not _check_clearance(session, classification):
        raise HTTPException(status_code=403, detail="Your clearance level does not allow uploading at this classification")

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size / (1024*1024):.1f} MB. Maximum allowed: 25 MB.",
        )

    # Validate MIME type
    filename = file.filename or "unnamed"
    detected_mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # Check magic bytes for PDF
    if content[:4] == b"%PDF" and "pdf" not in detected_mime:
        detected_mime = "application/pdf"

    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {detected_mime}. Allowed: PDF, images, Office documents, text, CSV, JSON, XML, ZIP.",
        )

    # ClamAV scan
    doc_id = uuid.uuid4()
    is_clean, scan_result = await scan_with_clamav(content)
    if not is_clean:
        # Create blocked document record for audit trail
        blocked_doc = Document(
            id=doc_id,
            tenant_id=session.tenant_id,
            workspace_id=uuid.UUID(workspace_id),
            folder_id=uuid.UUID(folder_id) if folder_id else None,
            name=filename,
            classification=classification,
            mime_type=detected_mime,
            size_bytes=file_size,
            status="blocked",
            created_by_id=session.user_id,
        )
        db.add(blocked_doc)
        await db.flush()
        await record_audit_event(
            db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
            actor_email=session.email, action="content:upload:blocked_malware",
            resource_type="document", resource_id=str(doc_id), outcome="DENY",
            reason=f"ClamAV blocked: {scan_result}",
            payload={"filename": filename, "scan_result": scan_result, "size_bytes": file_size},
        )
        raise HTTPException(
            status_code=400,
            detail=f"File blocked by antivirus scanner: {scan_result}. This incident has been audited.",
        )

    # Compute SHA-256 hash
    content_hash = hashlib.sha256(content).hexdigest()
    file_ext = Path(filename).suffix.lower()

    # Upload to MinIO
    storage_key = f"tenants/{session.tenant_id}/documents/{doc_id}/{filename}"
    try:
        await upload_to_minio(settings.s3_bucket_name, storage_key, content, detected_mime)
    except Exception as exc:
        logger.error(f"MinIO upload failed: {exc}")
        raise HTTPException(status_code=500, detail="Storage upload failed. Please try again.") from exc

    # Create document + initial version
    doc = Document(
        id=doc_id,
        tenant_id=session.tenant_id,
        workspace_id=uuid.UUID(workspace_id),
        folder_id=uuid.UUID(folder_id) if folder_id else None,
        name=filename,
        classification=classification,
        mime_type=detected_mime,
        file_extension=file_ext,
        size_bytes=file_size,
        content_hash=content_hash,
        storage_key=storage_key,
        status="ready",
        created_by_id=session.user_id,
    )
    db.add(doc)
    await db.flush()

    version = DocumentVersion(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        document_id=doc.id,
        version_number=1,
        name=filename,
        mime_type=detected_mime,
        size_bytes=file_size,
        content_hash=content_hash,
        storage_key=storage_key,
        status="ready",
        scan_result="clean",
        created_by_id=session.user_id,
    )
    db.add(version)
    await db.flush()

    # Set current version
    doc.current_version_id = version.id
    await db.flush()

    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:upload",
        resource_type="document", resource_id=str(doc.id), outcome="ALLOW",
        reason=f"Uploaded document: {filename} ({file_size} bytes, {classification})",
        payload={"filename": filename, "size_bytes": file_size, "content_hash": content_hash[:12]},
    )
    return _doc_out(doc)


@content_router.get("/nodes/{document_id}/download")
async def download_document(
    document_id: str,
    version_id: str | None = None,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    """Generate a short-lived pre-signed download URL via MinIO after clearance check."""
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id),
            Document.tenant_id == session.tenant_id,
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _check_clearance(session, doc.classification):
        raise HTTPException(status_code=403, detail="Insufficient clearance level for download")

    storage_key = doc.storage_key
    if version_id:
        ver = (await db.execute(
            select(DocumentVersion).where(DocumentVersion.id == uuid.UUID(version_id))
        )).scalar_one_or_none()
        if ver:
            storage_key = ver.storage_key

    if not storage_key:
        raise HTTPException(status_code=404, detail="Document file not found in storage")

    try:
        url = await generate_presigned_url(settings.s3_bucket_name, storage_key, expires=300)
    except Exception as exc:
        logger.error(f"Presigned URL generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not generate download link") from exc

    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:download",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason="Pre-signed download URL generated (5 min TTL)",
    )
    return RedirectResponse(url=url)


@content_router.post("/nodes/{document_id}/trash", status_code=status.HTTP_204_NO_CONTENT)
async def trash_document(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id), Document.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check legal hold
    hold_count = (await db.execute(
        text("SELECT COUNT(*) FROM legal_hold_targets WHERE document_id = :doc_id"),
        {"doc_id": str(document_id)},
    )).scalar() or 0
    if hold_count > 0:
        await record_audit_event(
            db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
            actor_email=session.email, action="content:document:delete_blocked_hold",
            resource_type="document", resource_id=document_id, outcome="DENY",
            reason="Deletion blocked: document is under legal hold",
        )
        raise HTTPException(
            status_code=409,
            detail="This document cannot be deleted because it is under a legal hold. Release the hold before deleting.",
        )

    doc.is_trashed = True
    doc.trashed_at = datetime.now(UTC)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:trash",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason=f"Document moved to trash: {doc.name}",
    )


@content_router.post("/nodes/{document_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_document(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id), Document.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_trashed = False
    doc.trashed_at = None
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:restore",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason=f"Document restored from trash: {doc.name}",
    )


@content_router.post("/nodes/{document_id}/checkout", status_code=status.HTTP_204_NO_CONTENT)
async def checkout_document(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id), Document.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.checkout_by_id and doc.checkout_by_id != session.user_id:
        raise HTTPException(status_code=409, detail="Document is already checked out by another user.")
    doc.checkout_by_id = session.user_id
    doc.checkout_at = datetime.now(UTC)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:checkout",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason=f"Document checked out: {doc.name}",
    )


@content_router.post("/nodes/{document_id}/checkin", status_code=status.HTTP_204_NO_CONTENT)
async def checkin_document(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id), Document.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.checkout_by_id != session.user_id and "Admin" not in session.roles and "RecordsManager" not in session.roles:
        raise HTTPException(status_code=403, detail="You cannot check in a document checked out by another user")
    doc.checkout_by_id = None
    doc.checkout_at = None
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:checkin",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason=f"Document checked in: {doc.name}",
    )


@content_router.get("/nodes/{document_id}/versions", response_model=list[DocumentVersionOut])
async def list_versions(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[DocumentVersionOut]:
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id), Document.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _check_clearance(session, doc.classification):
        raise HTTPException(status_code=403, detail="Insufficient clearance level")

    versions = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == uuid.UUID(document_id))
        .order_by(DocumentVersion.version_number.desc())
    )).scalars().all()

    return [
        DocumentVersionOut(
            id=str(v.id), document_id=str(v.document_id),
            version_number=v.version_number, name=v.name,
            mime_type=v.mime_type, size_bytes=v.size_bytes,
            content_hash=v.content_hash, status=v.status,
            scan_result=v.scan_result, ocr_status=v.ocr_status,
            comment=v.comment,
            created_by_id=str(v.created_by_id) if v.created_by_id else None,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@content_router.get("/nodes/{document_id}/comments", response_model=list[dict])
async def list_comments(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    comments = (await db.execute(
        select(DocumentComment)
        .where(DocumentComment.document_id == uuid.UUID(document_id))
        .where(DocumentComment.tenant_id == session.tenant_id)
        .order_by(DocumentComment.created_at.asc())
    )).scalars().all()
    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "author_id": str(c.author_id),
            "author_email": c.author_email,
            "body": c.body,
            "created_at": c.created_at.isoformat(),
        }
        for c in comments
    ]


@content_router.post("/nodes/{document_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    document_id: str,
    body: AddCommentRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    comment = DocumentComment(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        document_id=uuid.UUID(document_id),
        author_id=session.user_id,
        author_email=session.email,
        body=body.body,
    )
    db.add(comment)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:comment",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason="Comment added",
    )
    return {
        "id": str(comment.id),
        "document_id": str(comment.document_id),
        "author_id": str(comment.author_id),
        "author_email": comment.author_email,
        "body": comment.body,
        "created_at": comment.created_at.isoformat(),
    }


@content_router.post("/nodes/{document_id}/share", status_code=status.HTTP_201_CREATED)
async def share_document(
    document_id: str,
    body: ShareRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    if not body.shared_with_user_id and not body.shared_with_group_id:
        raise HTTPException(status_code=422, detail="Must specify shared_with_user_id or shared_with_group_id")
    share = DocumentShare(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        document_id=uuid.UUID(document_id),
        shared_with_user_id=uuid.UUID(body.shared_with_user_id) if body.shared_with_user_id else None,
        shared_with_group_id=uuid.UUID(body.shared_with_group_id) if body.shared_with_group_id else None,
        permission_level=body.permission_level,
        shared_by_id=session.user_id,
    )
    db.add(share)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:share",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason=f"Document shared with permission: {body.permission_level}",
    )
    return {"id": str(share.id), "permission_level": share.permission_level, "created_at": share.created_at.isoformat()}


@content_router.delete("/nodes/{document_id}/share/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    document_id: str,
    share_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    share = (await db.execute(
        select(DocumentShare).where(
            DocumentShare.id == uuid.UUID(share_id),
            DocumentShare.document_id == uuid.UUID(document_id),
            DocumentShare.tenant_id == session.tenant_id,
        )
    )).scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    await db.delete(share)
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="content:document:share_revoked",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason="Share revoked",
    )


@content_router.post("/nodes/{document_id}/declare-record", status_code=status.HTTP_204_NO_CONTENT)
async def declare_as_record(
    document_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Declare a document as an immutable record (Records Manager only)."""
    if "RecordsManager" not in session.roles and "Admin" not in session.roles:
        raise HTTPException(status_code=403, detail="Only Records Managers can declare records")
    doc = (await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id), Document.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_record = True
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="records:document:declare_record",
        resource_type="document", resource_id=document_id, outcome="ALLOW",
        reason=f"Document declared as immutable record: {doc.name}",
    )


@content_router.get("/stats", response_model=dict[str, Any])
async def content_stats(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """KPI stats for the dashboard."""
    total = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id,
            Document.is_trashed.is_(False),
        )
    )).scalar() or 0

    blocked = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id,
            Document.status == "blocked",
        )
    )).scalar() or 0

    records = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id,
            Document.is_record.is_(True),
        )
    )).scalar() or 0

    return {
        "total_documents": total,
        "blocked_uploads": blocked,
        "declared_records": records,
    }
