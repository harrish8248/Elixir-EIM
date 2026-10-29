"""OCR Processing Service using Tesseract OCR and PyMuPDF."""

import io
import os
import shutil
import time
import uuid

import pymupdf
import pytesseract  # type: ignore[import-untyped]
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.app.platform.config import settings
from apps.api.app.platform.logging import logger

# Configure tesseract executable path from settings / env / default locations
TESSERACT_CANDIDATES = [
    os.getenv("TESSERACT_CMD", ""),
    getattr(settings, "tesseract_cmd", ""),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    shutil.which("tesseract") or "",
]
TESSERACT_PATH = next(
    (p for p in TESSERACT_CANDIDATES if p and os.path.exists(p)),
    shutil.which("tesseract") or "tesseract",
)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Dedicated async engine for background OCR worker tasks
_ocr_engine = create_async_engine(settings.migration_database_url, pool_pre_ping=True)
_ocr_session_factory = async_sessionmaker(_ocr_engine, expire_on_commit=False)


async def process_document_ocr(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    content: bytes,
    mime_type: str,
    filename: str,
) -> None:
    """
    Background worker task to extract text via PyMuPDF (PDFs) and Tesseract OCR (images/scans).
    Updates document_text with extracted text, page count, confidence, language, and execution time.
    Also updates document status to ready and refreshes the PostgreSQL search_vector tsvector.
    """
    start_time = time.perf_counter()
    logger.info(f"Starting OCR processing for document {document_id} ({mime_type}, {len(content)} bytes)")

    async with _ocr_session_factory() as db:
        try:
            # Set initial processing status
            await db.execute(
                text(
                    """
                    INSERT INTO document_text (id, tenant_id, document_id, status, language, created_at, updated_at)
                    VALUES (:id, :tenant_id, :document_id, 'processing', 'eng', now(), now())
                    ON CONFLICT (document_id) DO UPDATE SET
                        status = 'processing',
                        updated_at = now()
                    """
                ),
                {"id": uuid.uuid4(), "tenant_id": tenant_id, "document_id": document_id},
            )
            await db.execute(
                text("UPDATE documents SET status = 'processing', updated_at = now() WHERE id = :id"),
                {"id": document_id},
            )
            await db.commit()

            # Execute extraction
            extracted_text = ""
            page_count = 1
            confidences: list[float] = []
            is_pdf = (mime_type == "application/pdf") or filename.lower().endswith(".pdf")

            if is_pdf:
                doc = pymupdf.open(stream=content, filetype="pdf")
                page_count = max(len(doc), 1)
                page_texts: list[str] = []

                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    native_text = page.get_text().strip()

                    # If page contains ample digital text, use native text layer
                    if len(native_text) >= 50:
                        page_texts.append(native_text)
                        confidences.append(98.5)
                    else:
                        # Rasterize sparse / scanned page and run Tesseract OCR
                        try:
                            pix = page.get_pixmap(dpi=150)
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            ocr_result = pytesseract.image_to_string(img)
                            page_texts.append(ocr_result.strip())

                            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                            word_confs = [float(c) for c in data["conf"] if float(c) > 0]
                            confidences.append(sum(word_confs) / len(word_confs) if word_confs else 85.0)
                        except Exception as ocr_err:
                            logger.warning(f"Page {page_idx} raster OCR fallback failed: {ocr_err}")
                            page_texts.append(native_text)
                            confidences.append(70.0)

                extracted_text = "\n\n".join(page_texts).strip()
                doc.close()

            elif mime_type.startswith("image/") or any(
                filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]
            ):
                img = Image.open(io.BytesIO(content))
                extracted_text = pytesseract.image_to_string(img).strip()

                try:
                    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    word_confs = [float(c) for c in data["conf"] if float(c) > 0]
                    confidences.append(sum(word_confs) / len(word_confs) if word_confs else 88.0)
                except Exception:
                    confidences.append(85.0)
                page_count = 1

            elif mime_type.startswith("text/") or any(
                filename.lower().endswith(ext) for ext in [".txt", ".md", ".json", ".csv", ".xml", ".html"]
            ):
                extracted_text = content.decode("utf-8", errors="ignore").strip()
                confidences.append(100.0)
                page_count = 1
            else:
                # Binary or unknown format
                extracted_text = f"Binary content: {filename} ({mime_type})"
                confidences.append(90.0)
                page_count = 1

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 90.0

            # Store in document_text
            await db.execute(
                text(
                    """
                    INSERT INTO document_text (
                        id, tenant_id, document_id, extracted_text, page_count,
                        confidence, language, processing_time_ms, ocr_engine,
                        status, updated_at
                    )
                    VALUES (
                        :id, :tenant_id, :document_id, :extracted_text, :page_count,
                        :confidence, 'eng', :elapsed_ms, 'tesseract-5.4.0+pymupdf',
                        'ready', now()
                    )
                    ON CONFLICT (document_id) DO UPDATE SET
                        extracted_text = :extracted_text,
                        page_count = :page_count,
                        confidence = :confidence,
                        processing_time_ms = :elapsed_ms,
                        status = 'ready',
                        error_message = NULL,
                        updated_at = now()
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "extracted_text": extracted_text,
                    "page_count": page_count,
                    "confidence": avg_confidence,
                    "elapsed_ms": elapsed_ms,
                },
            )

            # Update document status and search tsvector
            await db.execute(
                text(
                    """
                    UPDATE documents
                    SET status = 'ready',
                        search_vector = to_tsvector(
                            'english',
                            coalesce(name, '') || ' ' ||
                            coalesce(description, '') || ' ' ||
                            :extracted_text
                        ),
                        updated_at = now()
                    WHERE id = :document_id
                    """
                ),
                {
                    "document_id": document_id,
                    "extracted_text": extracted_text[:100000],  # cap at 100k chars for tsvector
                },
            )
            await db.commit()
            logger.info(
                f"OCR successfully completed for {document_id} in {elapsed_ms}ms "
                f"({page_count} pages, {len(extracted_text)} chars, conf={avg_confidence}%)"
            )

        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"OCR processing failed for document {document_id}: {exc}")
            await db.rollback()
            try:
                await db.execute(
                    text(
                        """
                        UPDATE document_text
                        SET status = 'failed',
                            error_message = :err,
                            processing_time_ms = :elapsed_ms,
                            updated_at = now()
                        WHERE document_id = :document_id
                        """
                    ),
                    {"document_id": document_id, "err": str(exc)[:500], "elapsed_ms": elapsed_ms},
                )
                await db.execute(
                    text("UPDATE documents SET status = 'failed', updated_at = now() WHERE id = :document_id"),
                    {"document_id": document_id},
                )
                await db.commit()
            except Exception as inner_err:
                logger.error(f"Failed to record OCR failure state: {inner_err}")
