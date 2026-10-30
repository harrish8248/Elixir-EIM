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
| **Content Repository** | Secure multi-tenant document explorer | Workspaces, folders, metadata tagging, ClamAV antivirus stream inspection |
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
4. **ClamAV Anti-Malware**: Pre-OCR stream inspection drops suspicious files before file writes or extraction.
5. **Cryptographic Audit Chain**: Events are sealed in an immutable hash chain ($H_n = \text{SHA256}(H_{n-1} \parallel \text{Event}_n)$).

---

## 🚀 Quickstart

### Prerequisites
- Windows 10/11 with Docker Desktop (WSL2 backend)
- Python 3.13+
- Node.js 20+
- Tesseract 5 (`winget install UB-Mannheim.TesseractOCR`)

### 1. Clone & Set Up Environment
```powershell
git clone https://github.com/harrish8248/Elixir-EIM.git
cd Elixir-EIM

# Python Virtual Environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock

# Web Application
npm --prefix apps/web install
```

### 2. Start Application
```powershell
.\start.ps1 -Demo
```

| Service | Endpoint |
|---|---|
| **Web Interface** | [http://localhost:5173](http://localhost:5173) |
| **FastAPI Swagger Docs** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| **Keycloak IAM** | [http://localhost:8080](http://localhost:8080) |

---

## 👥 Pre-Seeded Enterprise Personas

| Persona | Email | Role & Department | Clearance |
|---|---|---|---|
| **Sarah Chen** | `sarah.chen@acrocorp.com` | Global Administrator | Clearance 3 (Global) |
| **Raj Patel** | `raj.patel@acrocorp.com` | Finance Manager | Clearance 2 (Finance) |
| **Maria Santos** | `maria.santos@acrocorp.com` | HR Specialist | Clearance 1 (HR) |
| **Alex Auditor** | `alex.auditor@acrocorp.com` | Compliance Officer | Clearance 3 (Compliance) |

*Default password for all demo accounts:* `Password123!`

---

## 🧪 Verification & Testing

```powershell
# Run backend test suite
pytest apps/api/tests -v

# Verify architectural boundaries
lint-imports

# Verify OPA policy tests
docker exec elixir-opa opa test /policies -v

# Run frontend tests
npm --prefix apps/web test -- --run
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
