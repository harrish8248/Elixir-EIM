"""
Elixir EIM Resilient Enterprise Demo Store.
Provides high-fidelity, pre-seeded enterprise datasets for immediate UI rendering
when database queries are deferred or when database connectivity drops.
"""

import time
import uuid
from typing import Any

# AcroCorp Global Tenant ID
DEMO_TENANT_ID = "11111111-1111-1111-1111-111111111111"

# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------
DEMO_WORKSPACES = [
    {
        "id": "30000000-0000-0000-0000-000000000001",
        "tenant_id": DEMO_TENANT_ID,
        "name": "Global Operations",
        "description": "Finance, contracts, vendor invoices, and treasury documents",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "created_at": "2026-10-25T08:00:00Z",
        "updated_at": "2026-10-29T12:00:00Z",
    },
    {
        "id": "30000000-0000-0000-0000-000000000002",
        "tenant_id": DEMO_TENANT_ID,
        "name": "Human Resources",
        "description": "HR policies, personnel records, and employee onboarding",
        "classification": "INTERNAL",
        "department": "HR",
        "created_at": "2026-10-25T08:30:00Z",
        "updated_at": "2026-10-29T10:15:00Z",
    },
]

# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
DEMO_FOLDERS = [
    {
        "id": "40000000-0000-0000-0000-000000000001",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000001",
        "parent_id": None,
        "name": "Contracts & MSAs",
        "path": "/Contracts & MSAs",
        "created_at": "2026-10-25T09:00:00Z",
    },
    {
        "id": "40000000-0000-0000-0000-000000000002",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000002",
        "parent_id": None,
        "name": "Policies",
        "path": "/Policies",
        "created_at": "2026-10-25T09:15:00Z",
    },
    {
        "id": "40000000-0000-0000-0000-000000000003",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000001",
        "parent_id": None,
        "name": "Invoices & Receipts",
        "path": "/Invoices & Receipts",
        "created_at": "2026-10-25T09:30:00Z",
    },
]

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
DEMO_DOCUMENTS = [
    {
        "id": "50000000-0000-0000-0000-000000000001",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000001",
        "folder_id": "40000000-0000-0000-0000-000000000001",
        "name": "Q3 2026 Finance Report.pdf",
        "description": "Quarterly financial report with revenue, expenses and projections",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 245760,
        "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "status": "ready",
        "is_record": True,
        "is_trashed": False,
        "checkout_by_id": None,
        "checkout_at": None,
        "tags": ["Finance", "Q3", "SEC-17A4"],
        "version_count": 1,
        "created_by_id": "20000000-0000-0000-0000-000000000001",
        "created_at": "2026-10-26T10:00:00Z",
        "updated_at": "2026-10-29T14:30:00Z",
    },
    {
        "id": "50000000-0000-0000-0000-000000000002",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000001",
        "folder_id": "40000000-0000-0000-0000-000000000001",
        "name": "Vendor MSA — Acme Corp.pdf",
        "description": "Master Service Agreement with Acme Corporation, signed 2024",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 512000,
        "content_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef",
        "status": "ready",
        "is_record": True,
        "is_trashed": False,
        "checkout_by_id": None,
        "checkout_at": None,
        "tags": ["Vendor", "MSA", "Contract"],
        "version_count": 1,
        "created_by_id": "20000000-0000-0000-0000-000000000001",
        "created_at": "2026-10-26T11:00:00Z",
        "updated_at": "2026-10-28T09:20:00Z",
    },
    {
        "id": "50000000-0000-0000-0000-000000000003",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000001",
        "folder_id": "40000000-0000-0000-0000-000000000003",
        "name": "Invoice INV-2026-0892.pdf",
        "description": "Finance department invoice for Q3 enterprise software services",
        "classification": "CONFIDENTIAL",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 98304,
        "content_hash": "b2c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef12",
        "status": "ready",
        "is_record": False,
        "is_trashed": False,
        "checkout_by_id": None,
        "checkout_at": None,
        "tags": ["Invoice", "GST", "Vendor"],
        "version_count": 1,
        "created_by_id": "20000000-0000-0000-0000-000000000002",
        "created_at": "2026-10-27T14:10:00Z",
        "updated_at": "2026-10-29T16:00:00Z",
    },
    {
        "id": "50000000-0000-0000-0000-000000000004",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000002",
        "folder_id": "40000000-0000-0000-0000-000000000002",
        "name": "HR Policy Handbook 2026.pdf",
        "description": "Employee handbook and HR policies for 2026",
        "classification": "INTERNAL",
        "department": "HR",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 1048576,
        "content_hash": "c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef1234",
        "status": "ready",
        "is_record": True,
        "is_trashed": False,
        "checkout_by_id": None,
        "checkout_at": None,
        "tags": ["HR", "Handbook", "Policy"],
        "version_count": 1,
        "created_by_id": "20000000-0000-0000-0000-000000000003",
        "created_at": "2026-10-25T15:00:00Z",
        "updated_at": "2026-10-29T11:45:00Z",
    },
    {
        "id": "50000000-0000-0000-0000-000000000005",
        "tenant_id": DEMO_TENANT_ID,
        "workspace_id": "30000000-0000-0000-0000-000000000001",
        "folder_id": None,
        "name": "Public Annual Report 2025.pdf",
        "description": "Annual report for public corporate disclosure",
        "classification": "PUBLIC",
        "department": "Finance",
        "mime_type": "application/pdf",
        "file_extension": ".pdf",
        "size_bytes": 3145728,
        "content_hash": "d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef123456",
        "status": "ready",
        "is_record": True,
        "is_trashed": False,
        "checkout_by_id": None,
        "checkout_at": None,
        "tags": ["AnnualReport", "Public"],
        "version_count": 1,
        "created_by_id": "20000000-0000-0000-0000-000000000001",
        "created_at": "2026-10-25T16:00:00Z",
        "updated_at": "2026-10-28T18:00:00Z",
    },
]

# ---------------------------------------------------------------------------
# Capture & IDP Jobs
# ---------------------------------------------------------------------------
DEMO_CAPTURE_JOBS = [
    {
        "id": "job-inv-001",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000003",
        "filename": "gst_invoice_001_acrocorp.pdf",
        "status": "auto_approved",
        "document_type": "tax_invoice",
        "classification_confidence": 0.99,
        "ocr_engine": "indra",
        "mean_confidence": 0.97,
        "processing_time_ms": 1420.5,
        "created_at": "2026-10-29T10:14:00Z",
        "updated_at": "2026-10-29T10:14:02Z",
    },
    {
        "id": "job-inv-002",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000002",
        "filename": "gst_invoice_002_karnataka.pdf",
        "status": "auto_approved",
        "document_type": "tax_invoice",
        "classification_confidence": 0.98,
        "ocr_engine": "tesseract",
        "mean_confidence": 0.94,
        "processing_time_ms": 1850.0,
        "created_at": "2026-10-29T11:05:00Z",
        "updated_at": "2026-10-29T11:05:03Z",
    },
    {
        "id": "job-inv-003",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000001",
        "filename": "gst_invoice_003_checksum_mismatch.pdf",
        "status": "needs_review",
        "document_type": "tax_invoice",
        "classification_confidence": 0.96,
        "ocr_engine": "tesseract",
        "mean_confidence": 0.88,
        "processing_time_ms": 2100.2,
        "created_at": "2026-10-29T12:20:00Z",
        "updated_at": "2026-10-29T12:20:03Z",
    },
]

DEMO_IDP_STATS = {
    "total_jobs": 3,
    "status_counts": {
        "auto_approved": 2,
        "needs_review": 1,
        "completed": 0,
        "rejected": 0,
    },
    "stp_rate": 66.7,
    "avg_confidence": 93.0,
    "avg_latency_ms": 1790.2,
    "field_accuracy": 96.4,
}

DEMO_JOB_DETAILS = {
    "job-inv-001": {
        "id": "job-inv-001",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000003",
        "filename": "gst_invoice_001_acrocorp.pdf",
        "status": "auto_approved",
        "document_type": "tax_invoice",
        "classification_confidence": 0.99,
        "ocr_engine": "indra",
        "mean_confidence": 0.97,
        "processing_time_ms": 1420.5,
        "raw_text": "TAX INVOICE\nSupplier GSTIN: 27AAPFU0939F1ZV\nBuyer GSTIN: 29AABCI1234F1ZN\nInvoice No: INV-2026-0892\nTaxable: 12076.27\nCGST (9%): 1086.86\nSGST (9%): 1086.86\nTotal: 14250.00",
        "created_at": "2026-10-29T10:14:00Z",
        "updated_at": "2026-10-29T10:14:02Z",
        "fields": [
            {"field_name": "supplier_gstin", "field_value": "27AAPFU0939F1ZV", "normalized_value": "27AAPFU0939F1ZV", "confidence": 0.99, "page": 1, "bbox": [100, 200, 350, 230], "extraction_method": "regex", "is_valid": True, "error_message": None},
            {"field_name": "buyer_gstin", "field_value": "29AABCI1234F1ZN", "normalized_value": "29AABCI1234F1ZN", "confidence": 0.99, "page": 1, "bbox": [100, 240, 350, 270], "extraction_method": "regex", "is_valid": True, "error_message": None},
            {"field_name": "invoice_number", "field_value": "INV-2026-0892", "normalized_value": "INV-2026-0892", "confidence": 0.98, "page": 1, "bbox": [400, 200, 580, 230], "extraction_method": "key_value", "is_valid": True, "error_message": None},
            {"field_name": "invoice_date", "field_value": "2026-10-15", "normalized_value": "2026-10-15", "confidence": 0.98, "page": 1, "bbox": [400, 240, 580, 270], "extraction_method": "ner", "is_valid": True, "error_message": None},
            {"field_name": "taxable_amount", "field_value": "12076.27", "normalized_value": "12076.27", "confidence": 0.96, "page": 1, "bbox": [450, 600, 580, 625], "extraction_method": "table", "is_valid": True, "error_message": None},
            {"field_name": "cgst_amount", "field_value": "1086.86", "normalized_value": "1086.86", "confidence": 0.96, "page": 1, "bbox": [450, 630, 580, 655], "extraction_method": "table", "is_valid": True, "error_message": None},
            {"field_name": "sgst_amount", "field_value": "1086.86", "normalized_value": "1086.86", "confidence": 0.96, "page": 1, "bbox": [450, 660, 580, 685], "extraction_method": "table", "is_valid": True, "error_message": None},
            {"field_name": "total_amount", "field_value": "14250.00", "normalized_value": "14250.00", "confidence": 0.99, "page": 1, "bbox": [450, 700, 580, 730], "extraction_method": "table", "is_valid": True, "error_message": None},
        ],
        "validation_results": [
            {"rule_name": "gstin_checksum", "passed": True, "severity": "INFO", "message": "Supplier GSTIN 27AAPFU0939F1ZV passed Base-36 checksum (Maharashtra)"},
            {"rule_name": "tax_math", "passed": True, "severity": "INFO", "message": "Tax math verified: Taxable (12076.27) + CGST (1086.86) + SGST (1086.86) = Total (14250.00)"},
            {"rule_name": "po_matching", "passed": True, "severity": "INFO", "message": "Line items match purchase order PO-2026-9901 within 0.00 variance"},
        ],
    },
    "job-inv-003": {
        "id": "job-inv-003",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000001",
        "filename": "gst_invoice_003_checksum_mismatch.pdf",
        "status": "needs_review",
        "document_type": "tax_invoice",
        "classification_confidence": 0.96,
        "ocr_engine": "tesseract",
        "mean_confidence": 0.88,
        "processing_time_ms": 2100.2,
        "raw_text": "TAX INVOICE\nSupplier GSTIN: 27AAPFU0939F1ZX\nBuyer GSTIN: 29AABCI1234F1ZN\nInvoice No: INV-2026-0899\nTotal: 25000.00",
        "created_at": "2026-10-29T12:20:00Z",
        "updated_at": "2026-10-29T12:20:03Z",
        "fields": [
            {"field_name": "supplier_gstin", "field_value": "27AAPFU0939F1ZX", "normalized_value": "27AAPFU0939F1ZX", "confidence": 0.98, "page": 1, "bbox": [100, 200, 350, 230], "extraction_method": "regex", "is_valid": False, "error_message": "GSTIN Checksum Mismatch: Calculated 'V', found 'X'"},
            {"field_name": "buyer_gstin", "field_value": "29AABCI1234F1ZN", "normalized_value": "29AABCI1234F1ZN", "confidence": 0.98, "page": 1, "bbox": [100, 240, 350, 270], "extraction_method": "regex", "is_valid": True, "error_message": None},
            {"field_name": "total_amount", "field_value": "25000.00", "normalized_value": "25000.00", "confidence": 0.95, "page": 1, "bbox": [450, 700, 580, 730], "extraction_method": "table", "is_valid": True, "error_message": None},
        ],
        "validation_results": [
            {"rule_name": "gstin_checksum", "passed": False, "severity": "ERROR", "message": "GSTIN Checksum Mismatch: Calculated check digit 'V', found 'X' in document text"},
            {"rule_name": "human_review_required", "passed": False, "severity": "WARNING", "message": "Routed to Human Review Queue due to checksum failure"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Legal Holds & Retention Schedules
# ---------------------------------------------------------------------------
DEMO_LEGAL_HOLDS = [
    {
        "id": "60000000-0000-0000-0000-000000000001",
        "name": "DOJ Civil Inquiry - Case 891",
        "description": "Department of Justice civil inquiry requires preservation of all Finance Q3 records",
        "matter_number": "DOJ-CIVIL-891",
        "status": "ACTIVE",
        "placed_by_email": "sarah.chen@acrocorp.com",
        "released_at": None,
        "target_count": 2,
        "created_at": "2026-10-27T09:00:00Z",
    }
]

DEMO_RETENTION_SCHEDULES = [
    {
        "id": "70000000-0000-0000-0000-000000000001",
        "name": "SEC Rule 17a-4 Financial Records",
        "description": "7-year retention for financial records per SEC Rule 17a-4",
        "schedule_code": "SEC-17A4-7YR",
        "retention_years": 7,
        "department": "Finance",
        "classification": "CONFIDENTIAL",
        "is_active": True,
        "created_at": "2026-10-25T10:00:00Z",
    },
    {
        "id": "70000000-0000-0000-0000-000000000002",
        "name": "EEOC Personnel Files Retention",
        "description": "3-year retention for employee files and HR performance reviews",
        "schedule_code": "EEOC-HR-3YR",
        "retention_years": 3,
        "department": "HR",
        "classification": "INTERNAL",
        "is_active": True,
        "created_at": "2026-10-25T11:00:00Z",
    },
]

# ---------------------------------------------------------------------------
# Workflow Tasks
# ---------------------------------------------------------------------------
DEMO_WORKFLOW_TASKS = [
    {
        "id": "80000000-0000-0000-0000-000000000001",
        "document_id": "50000000-0000-0000-0000-000000000003",
        "document_name": "Invoice INV-2026-0892.pdf",
        "title": "Vendor Invoice Payment Approval — Acme Corp",
        "description": "Q3 Enterprise Software Services invoice awaiting manager review",
        "task_type": "approval",
        "status": "pending",
        "priority": "high",
        "submitted_by_email": "raj.patel@acrocorp.com",
        "assigned_to_email": "sarah.chen@acrocorp.com",
        "decision_by_email": None,
        "decision_at": None,
        "decision_reason": None,
        "due_date": "2026-11-05T17:00:00Z",
        "created_at": "2026-10-28T09:30:00Z",
        "updated_at": "2026-10-28T09:30:00Z",
    }
]

# ---------------------------------------------------------------------------
# Audit Events & Verification
# ---------------------------------------------------------------------------
DEMO_AUDIT_EVENTS = [
    {
        "id": "90000000-0000-0000-0000-000000000001",
        "tenant_id": DEMO_TENANT_ID,
        "sequence_number": 1,
        "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        "current_hash": "4a5e1e53b49ef633d9cbb28b889ebfe7e4e1df33b5c8be7c3c2f90a9b0123456",
        "timestamp": "2026-10-27T09:00:00Z",
        "actor_id": "20000000-0000-0000-0000-000000000001",
        "actor_email": "sarah.chen@acrocorp.com",
        "action": "records:legal_hold:create",
        "resource_type": "legal_hold",
        "resource_id": "60000000-0000-0000-0000-000000000001",
        "outcome": "ALLOW",
        "reason": "DOJ Civil Inquiry preservation order applied",
        "ip_address": "127.0.0.1",
        "correlation_id": "demo-audit-corr-1",
        "payload": {"matter": "DOJ-CIVIL-891"},
    },
    {
        "id": "90000000-0000-0000-0000-000000000002",
        "tenant_id": DEMO_TENANT_ID,
        "sequence_number": 2,
        "prev_hash": "4a5e1e53b49ef633d9cbb28b889ebfe7e4e1df33b5c8be7c3c2f90a9b0123456",
        "current_hash": "c8a1b2c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcd",
        "timestamp": "2026-10-28T09:30:00Z",
        "actor_id": "20000000-0000-0000-0000-000000000002",
        "actor_email": "raj.patel@acrocorp.com",
        "action": "workflow:task:submit",
        "resource_type": "workflow_task",
        "resource_id": "80000000-0000-0000-0000-000000000001",
        "outcome": "ALLOW",
        "reason": "Invoice INV-2026-0892 submitted for approval",
        "ip_address": "127.0.0.1",
        "correlation_id": "demo-audit-corr-2",
        "payload": {"amount": 14250.0},
    },
]

DEMO_AUDIT_SUMMARY = {
    "is_valid": True,
    "total_events": 2,
    "tenants_checked": 1,
    "violations": [],
}
