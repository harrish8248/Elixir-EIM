# Elixir EIM — Enterprise Capture & IDP Demonstration Guide

This guide walks through demonstrating the OpenText-style Capture and Intelligent Document Processing (IDP) module in Elixir EIM, featuring Vendor Invoice Management (VIM), multi-engine dynamic routing, Base-36 GSTIN checksum validation, and trigram fuzzy search.

---

## 1. Environment & Live URLs

| Service | URL | Status | Description |
| :--- | :--- | :--- | :--- |
| **Frontend Web App** | `http://localhost:5173` | **ONLINE** | React 18, Tailwind CSS, Vite dev server |
| **Backend REST API** | `http://127.0.0.1:8000` | **ONLINE** | FastAPI, Async SQLAlchemy, Redis session manager |
| **API Interactive Docs** | `http://127.0.0.1:8000/docs` | **ONLINE** | OpenAPI / Swagger specification |
| **Keycloak Identity** | `http://localhost:8080` | **ONLINE** | OIDC Authorization Server & JWKS issuer |
| **PostgreSQL 16** | `127.0.0.1:5432` | **ONLINE** | Multi-tenant schema with Row-Level Security (RLS) & `pg_trgm` |

---

## 2. Demo Personas & Login Credentials

Every persona can log in via Keycloak or via the **Quick Login** buttons on the login screen (`http://localhost:5173`):

| Persona | Email / Username | Password | Roles & Department | Clearance Level | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sarah Chen** | `sarah.chen@acrocorp.com` | `password123` | `RecordsManager`, `Finance` | **Level 3** | Full IDP dashboard, invoice validation, legal holds |
| **Raj Patel** | `raj.patel@acrocorp.com` | `password123` | `Employee`, `Finance` | **Level 2** | Finance invoices, tax workflows, cross-department ACL |
| **Maria Santos** | `maria.santos@acrocorp.com` | `password123` | `Employee`, `HR` | **Level 1** | HR records, employee files (Finance-restricted) |
| **Alex Auditor** | `alex.auditor@acrocorp.com` | `password123` | `Auditor`, `Compliance` | **Level 3** | Read-only ledger, tamper-proof hash chain verification |
| **System Admin** | `admin@acrocorp.com` | `password123` | `Admin`, `TenantAdmin`, `IT` | **Level 5** | OCR Engines Control Center, routing policies, tenant config |

---

## 3. Quick Verification Commands (CLI)

Run these commands from the repository root:

```bash
# 1. Run the Held-Out Test Split evaluation on the 440-doc benchmark
python cli/elixir_admin/main.py ocr evaluate --split test

# 2. Run the Held-Out Test Split evaluation on the Indian GST invoice benchmark
python cli/elixir_admin/main.py ocr evaluate --dataset gst --split test

# 3. Run the complete IDP unit test suite & regression gate (16 tests)
pytest apps/api/tests/test_idp_pipeline.py apps/api/tests/test_gstin_validation.py -v

# 4. Run the Trigram Fuzzy Search & Multi-Tenant ACL isolation tests
pytest apps/api/tests/test_search_acl_and_fuzzy.py -v

# 5. Reindex all repository documents with simple + english full-text vectors
python cli/elixir_admin/main.py reindex
```

---

## 4. Interactive Web Walkthrough

### Walkthrough 1: OCR Engines Control Center (`#/idp/engines`)
1. Log in as **System Admin** (`admin@acrocorp.com` / `password123`).
2. Click **"OCR Engines"** in the left sidebar under Primary Navigation.
3. **Observe the 8 Engine Cards**:
   - **PDF Text Layer (PyMuPDF)**: Native digital text extraction at $0.00$ CER and $35.4$ pages/sec.
   - **Indra OCR (v1.1.2 ONNX)**: Fast transformer OCR for Latin, Cyrillic, Greek, Devanagari, Bengali, Chinese (clean print only; not covering Tamil, Telugu, Kannada, Malayalam).
   - **Tesseract OCR (v5.5.0)**: Baseline workhorse with OpenCV preprocessing.
   - **PaddleOCR / docTR / EasyOCR / Surya / Ollama Vision**: Modular neural engines.
4. **Live Status & Dynamic Toggles**:
   - Click **"Refresh Engines Status"** to probe installed binaries, Python packages, and model weights in real time.
   - Toggle any engine ON or OFF. Changes are persisted to the database per tenant and immediately invalidate the Redis routing cache without restarting the server.
   - Edit the **Routing Policy** (Digital Threshold, Quality vs Speed priority) and observe the **Reset to Safe Defaults** one-click rollback.

---

### Walkthrough 2: Capture & IDP Dashboard (`#/idp`)
1. Log in as **Sarah Chen** (`sarah.chen@acrocorp.com` / `password123`).
2. Click **"Capture & IDP"** in the left sidebar.
3. **Observe Live Real-Time KPIs** (computed directly from PostgreSQL database rows):
   - **Straight-Through (STP) Rate**: Share of invoices meeting all confidence and business rules auto-approved without human intervention ($20.0\%$ baseline on general invoices, $100\%$ zero-false-approval on dev split).
   - **OCR Field Accuracy**: Real-time accuracy computed from reviewer corrections vs original extractions.
   - **Needs Review Queue**: Live counter of documents requiring manual human verification.
   - **Processing Latency**: Measured average end-to-end processing duration.
4. **Ingest a Document**:
   - Click **"Upload Document"** in the top-right header.
   - Select any sample document from `docs/ocr-benchmark/data/` or `docs/ocr-benchmark/data_gst/`.
   - The document undergoes ClamAV scanning, classification, adaptive OpenCV deskew/denoise, multi-pass OCR, and VIM validation.

---

### Walkthrough 3: Validation Workbench & Indian GST Invoices (`#/idp/workbench`)
1. In the Capture Jobs list, click **"Review"** on any invoice (or navigate to `#/idp/workbench?jobId=job-inv-001`).
2. **Left Pane (Interactive Document Canvas)**:
   - Use the zoom toolbar (`+`, `-`, `Reset`) to zoom into line items and tax summaries.
   - Visual bounding box overlays are synchronized with ground-truth and extracted fields ($91.1\%$ of fields achieve IoU $\ge 0.7$).
   - Click any bounding box on the canvas to instantly focus and highlight that field in the form.
3. **Right Pane (Vendor Invoice Management & GSTIN Engine)**:
   - **Base-36 Checksum Validation**:
     - View the supplier and buyer GSTIN badges. Valid GSTINs (e.g. `27AAPFU0939F1ZV`) display a green **"VALID CHECKSUM"** badge with state name resolution (Maharashtra).
     - Test invalid vectors (e.g. `27AAPFU0939F1ZX`) to observe the immediate red **"INVALID CHECKSUM"** alert.
   - **Mathematical Tax Reconciliation**:
     - Intra-state invoices: $CGST (9\%) + SGST (9\%) + \text{Taxable} = \text{Total Amount}$ ($IGST = 0.00$).
     - Inter-state invoices: $IGST (18\%) + \text{Taxable} = \text{Total Amount}$ ($CGST = SGST = 0.00$).
   - **Offline E-Invoice QR Verification**:
     - Decoded JWT payload displayed with digital invoice reference number (IRN) without external API calls.
   - **Reviewer Corrections & Continuous Learning**:
     - Edit any field (e.g. adjust Due Date), provide an audit justification, and click **"Save Corrections"**.
     - An immutable audit event (`IDP_FIELD_CORRECTED`) is appended to the SHA-256 chain, and the vendor template prior is updated in the database.

---

### Walkthrough 4: Trigram Fuzzy Search & ACL Isolation (`#/search`)
1. Press `Ctrl + K` anywhere in the application to summon the enterprise search modal.
2. Search for misspelled terms or partial codes (e.g. `"Acme Corp"`, `"27AAPFU0939"`, or `"Invioce"`).
3. **Features Demonstrated**:
   - **`pg_trgm` Fuzzy Matching**: Tolerates OCR misspellings and typos with trigram similarity scoring.
   - **Highlighted `<mark>` Snippets**: Matches are bolded and highlighted in the search excerpt.
   - **Multi-Tenant & Clearance Enforcement**:
     - Log in as **Raj Patel** (Finance, Clearance 2): Searches return finance invoices, vendor vouchers, and tax schedules.
     - Log in as **Maria Santos** (HR, Clearance 1): The same query strictly hides confidential finance records while returning HR policies, satisfying OPA PDP policy requirements.

---

### Walkthrough 5: Records Management & Process Automation (`#/records` & `#/workflow`)
1. Navigate to **"Records & Retention"** (`#/records`):
   - Review active Legal Holds, Retention Schedules, and the automated Disposition Queue.
   - Click **"New Legal Hold"** to place a litigation hold on any set of repository documents.
2. Navigate to **"Process Automation"** (`#/workflow`):
   - View pending multi-step approval workflows across departments.
   - Approve or reject document review tasks with an audit-logged reason.
