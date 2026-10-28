"""
Data models and schemas for Elixir EIM Intelligent Document Processing (IDP).
"""

from datetime import date, datetime
from enum import Enum
from typing import Any
import uuid
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, Enum):
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    ID_DOCUMENT = "id_document"
    OTHER = "other"


class BoundingBox(BaseModel):
    model_config = {"frozen": True}
    x: int
    y: int
    width: int
    height: int
    page: int = 1


class OcrWord(BaseModel):
    model_config = {"frozen": True}
    text: str
    confidence: float
    bbox: BoundingBox


class OcrPageResult(BaseModel):
    page_number: int
    width: int
    height: int
    full_text: str
    words: list[OcrWord] = []
    mean_confidence: float = 0.0
    engine: str = "tesseract"
    psm_used: int | None = None
    preprocessing_applied: list[str] = []


class OcrResult(BaseModel):
    pages: list[OcrPageResult] = []
    full_text: str = ""
    mean_confidence: float = 0.0
    engine: str = "tesseract"
    processing_time_ms: float = 0.0


class LineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    amount: float = 0.0
    confidence: float = 0.90
    bbox: BoundingBox | None = None


class ExtractedField(BaseModel):
    field_name: str
    field_value: Any
    confidence: float
    page: int = 1
    bbox: BoundingBox | None = None
    extraction_method: str = "heuristic"
    is_valid: bool = True
    error_message: str | None = None


class ValidationRuleResult(BaseModel):
    rule_name: str
    passed: bool
    message: str
    severity: str = "error"  # "error" | "warning" | "info"


class ValidationSummary(BaseModel):
    is_approved: bool
    status: JobStatus
    confidence_score: float
    rules: list[ValidationRuleResult] = []
    reasons: list[str] = []


class CaptureJobRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    status: JobStatus
    document_type: DocumentType
    classification_confidence: float
    ocr_engine: str
    processing_time_ms: float
    mean_confidence: float
    fields: dict[str, ExtractedField] = {}
    line_items: list[LineItem] = []
    validation_results: list[ValidationRuleResult] = []
    created_at: datetime
    updated_at: datetime


class FieldCorrectionRequest(BaseModel):
    field_name: str
    corrected_value: Any
    reason: str = "User manual correction"


class ValidateJobRequest(BaseModel):
    action: str  # "accept" | "reject" | "correct"
    corrections: list[FieldCorrectionRequest] = []
    comment: str | None = None
