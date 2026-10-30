# Elixir EIM (Enterprise Information Management)

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.13](https://img.shields.io/badge/Python-3.13-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg?logo=react&logoColor=white)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20RLS-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)

**Elixir EIM** is an enterprise-grade, multi-tenant document intelligence, compliance governance, and audit ledger platform. It features local zero-leakage OCR with specialized Indian GST invoice validation, tamper-evident hash-chained audit trails, DoD 5015.02 / ISO 15489 records retention, and zero-trust policy enforcement.

---

## ⚡ Core Capabilities

| Module | What It Does | Key Highlights |
|---|---|---|
| **Content Repository** | Secure multi-tenant document explorer | Workspaces, folders, metadata tagging, universal file intake, and quarantine management |
| **Universal File Intake** | Safe ingestion across 10+ formats | Binary magic bytes detection, archive bomb inspection, sandboxed extraction (PDF, DOCX, XLSX, ODT, HTML, RTF, EML) |
| **Upload Guardrails** | Enforced security & anti-malware pipeline | Fail-closed ClamAV streaming, DB-persisted tenant policies, zero-uninspected paths, hash-chained audit logging |
| **Sensitivity Classification** | Local explainable data governance | Algorithmic PII/Secrets/Indian ID detection (Verhoeff Aadhaar, Luhn card, Mod-36 GSTIN), auto clearance mapping |
| **Capture & IDP** | Intelligent Document Processing & VIM | Local multi-engine OCR (Tesseract, Indra, PyMuPDF), Base-36 GSTIN checksum validation, math reconciliation |
| **Human Workbench** | Side-by-side verification & correction | Bounding box highlighting, field corrections, auto-approval vs human-in-the-loop review |
| **OCR Engines Hub** | Adaptive multi-engine orchestration | Hardware-adaptive resource allocation (CPU/RAM/GPU), live accuracy metrics, automated failover |
| **Records & Retention** | DoD 5015.02 / ISO 15489 compliance | Immutable legal holds, defensible disposition schedules, audit-backed record declarations |
| **Process Automation** | Business approval workflows | Enforced separation of duties (no self-approval), multi-tier review chains |
| **Audit & Trust Ledger** | Cryptographic tamper-evident chain | Append-only SHA-256 hash chains, one-click verification, zero document text logged |

---

## 🛡️ Security & Architecture

1. **Zero-Trust PEP/PDP**: Every request is evaluated by Open Policy Agent (OPA). Unreachable OPA defaults strictly to `DENY`.
2. **PostgreSQL RLS**: Hardware-enforced row-level security (`app.current_tenant_id`) guarantees strict multi-tenant isolation.
3. **Local Zero-Leakage OCR**: Document processing runs 100% locally on-premise without external cloud API calls.
4. **Universal File Intake Pipeline**:
   ```
   [Stream Size Check] ──> [Binary Magic Bytes] ──> [Archive Inspection]
                                                          │
   [Postgres / MinIO] <── [Classify & Mask] <── [Extract] <── [Fail-Closed ClamAV]
   ```
5. **Strict Fail-Closed Antivirus**: Pre-OCR ClamAV stream inspection is a non-negotiable server invariant. Scanner timeout, daemon crash, or malware detection strictly aborts ingestion with HTTP 503/422, stores zero bytes in MinIO, and records a hash-chained audit event.
6. **Cryptographic Audit Chain**: Events are sealed in an immutable append-only hash chain ($H_n = \text{SHA256}(H_{n-1} \parallel \text{Event}_n)$), with zero raw document text in logs.

---

## 🔬 Enterprise File Intake & Guardrails

### 1. Universal Type Detection & Archive Security
- **Magic Bytes Sniffing:** Determines true file MIME types from header bytes rather than untrusted extensions. Detects PE/MZ (`.exe`, `.dll`, `.msi`), scripts (`.bat`, `.sh`, `.ps1`), macros (`.docm`, `.xlsm`), PDF, Office XML, ODT, HTML, CSV, JSON, and media.
- **Archive Limits (Zip-Bomb Defense):** Inspects zip, tar, gz, and 7z archives with strict limits: recursion depth &le; 3, member count &le; 1,000, uncompressed size &le; 200 MB, and compression ratio &le; 150:1. Encrypted archives that cannot be scanned are automatically blocked.
- **Sandboxed Text Extraction:** 10s per-parser timeout across 10+ formats (PDF, DOCX, XLSX, PPTX, ODT, HTML, RTF, EML, CSV, JSON, TXT). Audio/Video/CAD files are securely classified with metadata-only fallback.

### 2. Tenant Guardrails & Quarantine Queue
- **Persisted Tenant Policy:** Stored in the `tenant_guardrails` PostgreSQL table and managed via `GET /api/v1/guardrails/policy` and `PUT /api/v1/guardrails/policy` (admin-only, protected by PEP/OPA with before/after audit tracking).
- **Quarantine Workflow:** Files triggering quarantine rules are safely isolated in the `quarantine_items` table. Administrators inspect metadata, release (`POST /api/v1/guardrails/quarantine/{id}/release`), or permanently purge (`DELETE /api/v1/guardrails/quarantine/{id}`) quarantined assets.

### 3. Local Explainable Sensitivity Classification
- **Algorithmic Detectors:**
  - **Indian Identifiers:** PAN format, Aadhaar with 12-digit Verhoeff checksum algorithm, GSTIN with official Base-36 checksum, IFSC, Indian mobile numbers.
  - **Financial Data:** Credit/Debit card numbers with Luhn Mod-10 algorithm, bank account numbers near keywords, UPI handles.
  - **Secrets & Keys:** PEM private keys, AWS access keys, GitHub personal access tokens, Slack tokens, JWTs, config passwords.
  - **PII & Legal:** Personal emails, dates of birth, postal addresses, payroll/salary figures, medical records, and NDAs.
- **Clearance Mapping:**
  | Sensitivity Label | Document Clearance | Access Restriction |
  |---|---|---|
  | `SAFE` | `PUBLIC` or `INTERNAL` | Accessible across authorized workspace employees |
  | `SENSITIVE` | `CONFIDENTIAL` | Restricted to departmental managers and cleared personnel |
  | `CRITICAL` | `RESTRICTED` | High-security containment requiring executive clearance |
- **Evaluation Accuracy:** Evaluated on a 160-file synthetic multi-format corpus with **95.00% overall accuracy** and **94.90% macro F1** on the held-out test split (100% rejection of corrupt Verhoeff/Luhn/GSTIN checksums).

---

## ⚙️ Host-Adaptive OCR Engine Orchestration

The IDP engine (`OcrEnginesControlCenterView.tsx`) dynamically profiles the host machine to eliminate single-vendor dependency and prevent system freezing:
- **Probed Hardware Telemetry:** Directly queries physical/logical cores, available RAM, GPU presence, and battery power status.
- **Dynamic Speed Decider:** Low-end machines (low RAM/battery) dynamically downsample render resolution to 200 DPI and throttle thread pools; high-tier machines enable parallel neural passes.
- **Fallback Cascade:** Born-Digital PyMuPDF Vector Layer (0.08s) &rarr; Indra Indic CPU Transformer (0.65s) &rarr; Tesseract 5 + OpenCV Deskew/CLAHE (1.20s) &rarr; Human Review Workbench.

---

## 👥 Pre-Seeded Enterprise Personas

| Persona | Email | Role & Department | Clearance | Default Access Scope |
|---|---|---|---|---|
| **Sarah Chen** | `sarah.chen@acrocorp.com` | Tenant Administrator | Clearance 3 (Global) | Universal repository & guardrail administration |
| **Raj Patel** | `raj.patel@acrocorp.com` | Finance Manager | Clearance 2 (Finance) | Finance workspaces, invoices, P&L statements |
| **Maria Santos** | `maria.santos@acrocorp.com` | HR Specialist | Clearance 1 (HR) | HR records, employee handbooks, compensation |
| **Alex Auditor** | `alex.auditor@acrocorp.com` | Compliance Officer | Clearance 3 (Compliance) | Read-only access to cryptographic audit trails |

*Standard password for all demo accounts:* `Password123!` (or `password123`)

---

## 🧪 Verification & Testing Commands

```powershell
# 1. Run Vitest component & UI test suite
npm --prefix apps/web test -- --run

# 2. Run Ruff linter on backend
.venv\Scripts\ruff check apps/api

# 3. Run Mypy static type checker
.venv\Scripts\mypy apps/api

# 4. Verify multi-department search facet ACL isolation
.venv\Scripts\python scripts/verify_search_facets.py

# 5. Verify 15 seeded GSTINs with Base-36 checksum validator
.venv\Scripts\python scripts/verify_all_gstins.py

# 6. Run synthetic corpus sensitivity evaluation on held-out split
.venv\Scripts\python scripts/generate_synthetic_corpus.py

# 7. Run full backend pytest suite
.venv\Scripts\pytest apps/api/tests -v
```

---

## 📂 Repository Structure

```
├── apps/
│   ├── api/             # FastAPI backend (Identity, PEP, Content, IDP, Records, Workflow, Audit)
│   └── web/             # React + Vite + TypeScript enterprise frontend
├── cli/elixir_admin/    # elixir-admin management CLI tool
├── docs/                # Architectural specifications, benchmark docs, compliance references
├── deployment/          # Docker Compose manifests and service configurations
├── policies/            # Rego OPA security & authorization policies
└── scripts/             # Seed data and transparent benchmark dataset loader
```

---

## 📄 License

Licensed under the [Apache License, Version 2.0](LICENSE). Third-party OCR engines and model weights adhere to their respective licenses (see [THIRD_PARTY_LICENSES.md](docs/THIRD_PARTY_LICENSES.md)).
