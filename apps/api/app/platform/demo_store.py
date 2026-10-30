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
# ---------------------------------------------------------------------------
# Capture & IDP Jobs
# ---------------------------------------------------------------------------
DEMO_CAPTURE_JOBS = [
    {
        "id": "job-sbc-0590",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000001",
        "filename": "SBC-0590_Sri_Balaji_Computers_TamilNadu.pdf",
        "status": "needs_review",
        "document_type": "tax_invoice",
        "classification_confidence": 0.98,
        "ocr_engine": "tesseract",
        "mean_confidence": 0.94,
        "processing_time_ms": 1640.0,
        "created_at": "2026-10-29T12:20:00Z",
        "updated_at": "2026-10-29T12:20:03Z",
    },
    {
        "id": "job-inv-0892",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000003",
        "filename": "INV-2026-0892_Infosys_Technologies.pdf",
        "status": "auto_approved",
        "document_type": "tax_invoice",
        "classification_confidence": 0.99,
        "ocr_engine": "indra",
        "mean_confidence": 0.98,
        "processing_time_ms": 1220.5,
        "created_at": "2026-10-29T10:14:00Z",
        "updated_at": "2026-10-29T10:14:02Z",
    },
    {
        "id": "job-tcs-4410",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000002",
        "filename": "TCS-2026-4410_Tata_Consultancy_Services.pdf",
        "status": "completed",
        "document_type": "tax_invoice",
        "classification_confidence": 1.0,
        "ocr_engine": "pymupdf",
        "mean_confidence": 0.99,
        "processing_time_ms": 420.0,
        "created_at": "2026-10-29T09:05:00Z",
        "updated_at": "2026-10-29T09:15:00Z",
    },
]

DEMO_IDP_STATS = {
    "has_data": True,
    "total_documents": 3,
    "stp_rate_pct": 66.7,
    "average_confidence_pct": 97.0,
    "average_processing_time_ms": 1093.5,
    "review_queue_size": 1,
    "auto_approved_count": 1,
    "completed_count": 1,
    "rejected_count": 0,
    "correction_accuracy_pct": 98.2,
    "total_human_corrections": 1,
    "total_extracted_fields": 54,
}

RAW_TEXT_SBC = """TAX INVOICE / CASH BILL
SRI BALAJI COMPUTERS
72, SARATHY NAGAR, KAGITHAPATTARI
VELLORE - 632012
GSTIN/UIN: 33AAQPK8576K1ZY
State Name: Tamil Nadu, Code: 33
E-Mail: bcitvir@gmail.com

Buyer (Bill to):
S2 INTEGRATORS PVT LTD
547, ANNA SALAI, NANDANAM, CHENNAI
GSTIN/UIN: 33AABCU8048A1Z0
State Name: Tamil Nadu, Code: 33

Invoice No: SBC/0590/2026-27      Dated: 5-Jun-26
Delivery Note:                     Mode/Terms of Payment:
Reference No. & Date:              Other References:
Dispatch Doc No:                   Delivery Note Date:
Dispatched through:                Destination:
Terms of Delivery:

Sl. Particulars                      HSN/SAC   Quantity  Rate per     Amount
1   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    Mr. RISHMA, LENOVO T14
2   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    Mr. SYED IDROSE, DELL LATITUDE 5411
3   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    FAZIL, DELL LATITUDE 5411
4   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    RAGA PRIYA, DELL LATITUDE 5411
5   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    Ms. RENUGADEVI SALEM, LENOVO IDEAPAD 3

                                     SGST 9%                          1,575.00
                                     CGST 9%                          1,575.00
                                     Total                           20,650.00

Amount Chargeable (in words):
INR Twenty Thousand Six Hundred Fifty Only
"""

DEMO_JOB_DETAILS = {
    "job-sbc-0590": {
        "id": "job-sbc-0590",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000001",
        "filename": "SBC-0590_Sri_Balaji_Computers_TamilNadu.pdf",
        "status": "needs_review",
        "document_type": "TAX INVOICE / CASH BILL",
        "classification_confidence": 0.98,
        "ocr_engine": "Tesseract 5.4.0 (eng + tam)",
        "mean_confidence": 0.94,
        "processing_time_ms": 1640.0,
        "raw_text": RAW_TEXT_SBC,
        "created_at": "2026-10-29T12:20:00Z",
        "updated_at": "2026-10-29T12:20:03Z",
        "fields": [
            {"field_name": "supplier_gstin", "field_value": "33AAQPK8576K1ZY", "normalized_value": "33AAQPK8576K1ZY", "confidence": 0.96, "page": 1, "bbox": [70, 115, 180, 20], "extraction_method": "regex_base36", "is_valid": True, "error_message": None},
            {"field_name": "buyer_gstin", "field_value": "33AABCU8048A1Z0", "normalized_value": "33AABCU8048A1Z0", "confidence": 0.96, "page": 1, "bbox": [70, 260, 180, 20], "extraction_method": "regex_base36", "is_valid": False, "error_message": "GSTIN Check Character Mismatch: OCR read '0', expected 'O'. Please confirm with original document."},
            {"field_name": "supplier_name", "field_value": "SRI BALAJI COMPUTERS", "normalized_value": "SRI BALAJI COMPUTERS", "confidence": 0.88, "page": 1, "bbox": [70, 70, 220, 22], "extraction_method": "layout_header", "is_valid": True, "error_message": None},
            {"field_name": "buyer_name", "field_value": "S2 INTEGRATORS PVT LTD", "normalized_value": "S2 INTEGRATORS PVT LTD", "confidence": 0.85, "page": 1, "bbox": [70, 220, 220, 20], "extraction_method": "layout_header", "is_valid": True, "error_message": None},
            {"field_name": "supplier_address", "field_value": "72, SARATHY NAGAR, KAGITHAPATTARI, VELLORE - 632012", "normalized_value": "72, SARATHY NAGAR, VELLORE - 632012", "confidence": 0.82, "page": 1, "bbox": [70, 92, 280, 18], "extraction_method": "address_ner", "is_valid": True, "error_message": None},
            {"field_name": "buyer_address", "field_value": "547, ANNA SALAI, NANDANAM, CHENNAI", "normalized_value": "547, ANNA SALAI, CHENNAI", "confidence": 0.75, "page": 1, "bbox": [70, 240, 260, 18], "extraction_method": "address_ner", "is_valid": True, "error_message": None},
            {"field_name": "invoice_number", "field_value": "SBC/0590/2026-27", "normalized_value": "SBC/0590/2026-27", "confidence": 0.92, "page": 1, "bbox": [240, 165, 140, 20], "extraction_method": "key_value", "is_valid": True, "error_message": None},
            {"field_name": "invoice_date", "field_value": "2026-06-05", "normalized_value": "2026-06-05", "confidence": 0.95, "page": 1, "bbox": [320, 165, 90, 20], "extraction_method": "date_parser", "is_valid": True, "error_message": None},
            {"field_name": "due_date", "field_value": "2026-07-05", "normalized_value": "2026-07-05", "confidence": 0.90, "page": 1, "bbox": [320, 185, 90, 20], "extraction_method": "date_offset", "is_valid": True, "error_message": None},
            {"field_name": "po_number", "field_value": "PO-2026-881", "normalized_value": "PO-2026-881", "confidence": 0.85, "page": 1, "bbox": [240, 235, 120, 18], "extraction_method": "pattern", "is_valid": True, "error_message": None},
            {"field_name": "currency", "field_value": "INR", "normalized_value": "INR", "confidence": 0.99, "page": 1, "bbox": [20, 800, 40, 15], "extraction_method": "anchor", "is_valid": True, "error_message": None},
            {"field_name": "contact_details", "field_value": "bcitvir@gmail.com", "normalized_value": "bcitvir@gmail.com", "confidence": 0.95, "page": 1, "bbox": [70, 145, 160, 16], "extraction_method": "email_regex", "is_valid": True, "error_message": None},
            {"field_name": "taxable_amount", "field_value": "17500.00", "normalized_value": "17500.00", "confidence": 0.97, "page": 1, "bbox": [350, 715, 80, 20], "extraction_method": "table_sum", "is_valid": True, "error_message": None},
            {"field_name": "cgst_amount", "field_value": "1575.00", "normalized_value": "1575.00", "confidence": 0.96, "page": 1, "bbox": [350, 740, 80, 20], "extraction_method": "tax_rate", "is_valid": True, "error_message": None},
            {"field_name": "sgst_amount", "field_value": "1575.00", "normalized_value": "1575.00", "confidence": 0.96, "page": 1, "bbox": [350, 765, 80, 20], "extraction_method": "tax_rate", "is_valid": True, "error_message": None},
            {"field_name": "total_amount", "field_value": "20650.00", "normalized_value": "20650.00", "confidence": 0.99, "page": 1, "bbox": [350, 790, 80, 22], "extraction_method": "table_total", "is_valid": True, "error_message": None},
        ],
        "validation_results": [
            {"rule_name": "GSTIN_CHECKSUM_SUPPLIER", "passed": True, "severity": "INFO", "message": "Supplier GSTIN '33AAQPK8576K1ZY' Base-36 checksum validated (Tamil Nadu - State 33)"},
            {"rule_name": "GSTIN_CHECKSUM_BUYER", "passed": False, "severity": "WARNING", "message": "Buyer GSTIN '33AABCU8048A1Z0' Check Digit Warning: Expected 'O', OCR extracted '0'. Awaiting human sign-off."},
            {"rule_name": "TAX_MATH_RECONCILIATION", "passed": True, "severity": "INFO", "message": "Tax math exact: Taxable (17,500.00) + CGST 9% (1,575.00) + SGST 9% (1,575.00) == Total (20,650.00)"},
        ],
    },
    "job-inv-0892": {
        "id": "job-inv-0892",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000003",
        "filename": "INV-2026-0892_Infosys_Technologies.pdf",
        "status": "auto_approved",
        "document_type": "B2B GST Tax Invoice",
        "classification_confidence": 0.99,
        "ocr_engine": "Indra OCR v1.0.0 (fast CPU)",
        "mean_confidence": 0.98,
        "processing_time_ms": 1220.5,
        "raw_text": "TAX INVOICE / GST INVOICE\nSupplier: Infosys Technologies Pvt Ltd\nGSTIN: 29AABCI1234F1ZX (Karnataka)\nBuyer: AcroCorp India Private Limited\nGSTIN: 27AABCA9876M1ZY (Maharashtra)\nInvoice No: INV-2026-0892\nDate: 2026-04-05\nTaxable Value: 365000.00\nIGST (18%): 65700.00\nTotal Amount: 430700.00",
        "created_at": "2026-10-29T10:14:00Z",
        "updated_at": "2026-10-29T10:14:02Z",
        "fields": [
            {"field_name": "supplier_gstin", "field_value": "29AABCI1234F1ZX", "normalized_value": "29AABCI1234F1ZX", "confidence": 0.99, "page": 1, "bbox": [77, 113, 76, 6], "extraction_method": "gstin_repair_checksum", "is_valid": True, "error_message": None},
            {"field_name": "buyer_gstin", "field_value": "27AABCA9876M1ZY", "normalized_value": "27AABCA9876M1ZY", "confidence": 0.99, "page": 1, "bbox": [77, 251, 82, 6], "extraction_method": "gstin_repair_checksum", "is_valid": True, "error_message": None},
            {"field_name": "supplier_name", "field_value": "INFOSYS TECHNOLOGIES PVT LTD", "normalized_value": "INFOSYS TECHNOLOGIES PVT LTD", "confidence": 0.98, "page": 1, "bbox": [77, 90, 180, 8], "extraction_method": "header_ner", "is_valid": True, "error_message": None},
            {"field_name": "buyer_name", "field_value": "ACROCORP INDIA PRIVATE LIMITED", "normalized_value": "ACROCORP INDIA PRIVATE LIMITED", "confidence": 0.98, "page": 1, "bbox": [77, 230, 180, 8], "extraction_method": "header_ner", "is_valid": True, "error_message": None},
            {"field_name": "invoice_number", "field_value": "INV-2026-0892", "normalized_value": "INV-2026-0892", "confidence": 0.99, "page": 1, "bbox": [113, 173, 58, 7], "extraction_method": "regex_pattern", "is_valid": True, "error_message": None},
            {"field_name": "invoice_date", "field_value": "2026-04-05", "normalized_value": "2026-04-05", "confidence": 0.98, "page": 1, "bbox": [326, 173, 44, 7], "extraction_method": "iso_date_regex", "is_valid": True, "error_message": None},
            {"field_name": "taxable_amount", "field_value": "365000.00", "normalized_value": "365000.00", "confidence": 0.98, "page": 1, "bbox": [717, 407, 42, 8], "extraction_method": "amount_proximity", "is_valid": True, "error_message": None},
            {"field_name": "igst_amount", "field_value": "65700.00", "normalized_value": "65700.00", "confidence": 0.97, "page": 1, "bbox": [717, 420, 35, 8], "extraction_method": "tax_breakdown", "is_valid": True, "error_message": None},
            {"field_name": "total_amount", "field_value": "430700.00", "normalized_value": "430700.00", "confidence": 0.99, "page": 1, "bbox": [719, 437, 53, 9], "extraction_method": "total_amount_scan", "is_valid": True, "error_message": None},
            {"field_name": "currency", "field_value": "INR", "normalized_value": "INR", "confidence": 0.99, "page": 1, "bbox": [710, 437, 8, 9], "extraction_method": "anchor", "is_valid": True, "error_message": None},
        ],
        "validation_results": [
            {"rule_name": "GSTIN_CHECKSUM_VALIDATION", "passed": True, "severity": "INFO", "message": "Supplier GSTIN '29AABCI1234F1ZX' validated with official Base-36 checksum (Karnataka)"},
            {"rule_name": "GSTIN_BUYER_CHECKSUM_VALIDATION", "passed": True, "severity": "INFO", "message": "Buyer GSTIN '27AABCA9876M1ZY' validated with official Base-36 checksum (Maharashtra)"},
            {"rule_name": "GST_TAX_RECONCILIATION", "passed": True, "severity": "INFO", "message": "Taxable (365,000.00) + Integrated GST 18% (65,700.00) == Total (430,700.00)"},
            {"rule_name": "IRN_E_INVOICE_QR_VERIFIED", "passed": True, "severity": "INFO", "message": "Signed e-Invoice JWT QR code decoded offline; seller, buyer, doc_no match 100%"},
        ],
    },
    "job-tcs-4410": {
        "id": "job-tcs-4410",
        "tenant_id": DEMO_TENANT_ID,
        "document_id": "50000000-0000-0000-0000-000000000002",
        "filename": "TCS-2026-4410_Tata_Consultancy_Services.pdf",
        "status": "completed",
        "document_type": "Corporate Tax Invoice",
        "classification_confidence": 1.0,
        "ocr_engine": "PyMuPDF (Vector Text Layer)",
        "mean_confidence": 0.99,
        "processing_time_ms": 420.0,
        "raw_text": "TAX INVOICE\nSupplier: Tata Consultancy Services\nGSTIN: 27AAPFU0939F1ZX (Maharashtra)\nBuyer: Delhi Telecom Limited\nGSTIN: 07AAACH2345J1ZW (Delhi)\nInvoice No: TCS-2026-4410\nDate: 2026-05-18\nTotal Amount: 1250000.00",
        "created_at": "2026-10-29T09:05:00Z",
        "updated_at": "2026-10-29T09:15:00Z",
        "fields": [
            {"field_name": "supplier_gstin", "field_value": "27AAPFU0939F1ZX", "normalized_value": "27AAPFU0939F1ZX", "confidence": 0.99, "page": 1, "bbox": [100, 100, 150, 15], "extraction_method": "vector_pdf", "is_valid": True, "error_message": None},
            {"field_name": "buyer_gstin", "field_value": "07AAACH2345J1ZW", "normalized_value": "07AAACH2345J1ZW", "confidence": 0.99, "page": 1, "bbox": [100, 200, 150, 15], "extraction_method": "vector_pdf", "is_valid": True, "error_message": None},
            {"field_name": "supplier_name", "field_value": "TATA CONSULTANCY SERVICES", "normalized_value": "TATA CONSULTANCY SERVICES", "confidence": 1.0, "page": 1, "bbox": [100, 80, 200, 15], "extraction_method": "vector_pdf", "is_valid": True, "error_message": None},
            {"field_name": "buyer_name", "field_value": "DELHI TELECOM LIMITED", "normalized_value": "DELHI TELECOM LIMITED", "confidence": 1.0, "page": 1, "bbox": [100, 180, 200, 15], "extraction_method": "vector_pdf", "is_valid": True, "error_message": None},
            {"field_name": "invoice_number", "field_value": "TCS-2026-4410", "normalized_value": "TCS-2026-4410", "confidence": 1.0, "page": 1, "bbox": [300, 120, 100, 15], "extraction_method": "vector_pdf", "is_valid": True, "error_message": None},
            {"field_name": "total_amount", "field_value": "1250000.00", "normalized_value": "1250000.00", "confidence": 1.0, "page": 1, "bbox": [400, 500, 100, 18], "extraction_method": "vector_pdf", "is_valid": True, "error_message": None},
        ],
        "validation_results": [
            {"rule_name": "VECTOR_TEXT_VALIDATION", "passed": True, "severity": "INFO", "message": "High fidelity native vector PDF text layer decoded; 100% character integrity"},
            {"rule_name": "HUMAN_SIGN_OFF", "passed": True, "severity": "INFO", "message": "Review completed and approved by Finance Lead on 2026-10-29"},
        ],
    },
}

# Aliases for legacy IDs
DEMO_JOB_DETAILS["job-inv-001"] = DEMO_JOB_DETAILS["job-inv-0892"]
DEMO_JOB_DETAILS["job-inv-002"] = DEMO_JOB_DETAILS["job-tcs-4410"]
DEMO_JOB_DETAILS["job-inv-003"] = DEMO_JOB_DETAILS["job-sbc-0590"]

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
