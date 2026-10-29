# Architecture Decision Records (ADRs)

## ADR 001: Modular Monolith Architecture
- **Status:** Accepted
- **Context:** Enterprise information management suites require rich data relationships (documents, records, workflows, audit) with strict transaction boundaries. Microservices introduce premature network latency, distributed transaction complexity, and data consistency risks.
- **Decision:** Build Elixir EIM 1.0 as a modular monolith in Python/FastAPI with transactional outbox events, strict domain separation enforced by import-linter, and an extensible plugin system.
- **Consequences:** Low operational complexity, transactional consistency for audit and outbox events, clean migration path to independent services in future releases if justified.

## ADR 002: Cross-Cutting Trust Layer with PEP/PDP
- **Status:** Accepted
- **Context:** Security and governance must be uniformly applied across all content, records, workflows, and administration routes without code duplication or developer oversight.
- **Decision:** Implement a centralized Policy Enforcement Point (PEP) that queries a Policy Decision Point (PDP) backed by Open Policy Agent (OPA) Rego rules. Guardrails and audit are integrated into this single decision flow.
- **Consequences:** All routes are protected by default; policies can be tested, versioned, and simulated independently of application code.

## ADR 003: Expand/Contract Database Evolution
- **Status:** Accepted
- **Context:** Enterprise deployments require zero downtime during maintenance and upgrades.
- **Decision:** All database migrations must follow the expand/contract pattern. Breaking column or table drops are deferred by at least one minor release cycle.
- **Consequences:** Deployments are rollback-safe and can run blue/green versions concurrently against the same database.

## ADR 004: Single Source of Truth for Product Branding
- **Status:** Accepted
- **Context:** Enterprise clients frequently require re-branding, OEM packaging, or tenant white-labeling. Hardcoded strings across code and UI break consistency.
- **Decision:** Define all branding constants (`name`, `short_name`, `version`, `vendor`) in `platform.branding.ProductBrandingConfig`.
- **Consequences:** Single-point modifications update API headers, telemetry, error envelopes, and UI chrome automatically.

## ADR 005: Python 3.13 Standardized Runtime Target
- **Status:** Accepted
- **Context:** Elixir EIM 1.0 requires high-throughput asynchronous execution, enhanced memory safety, and modern type annotations across its enterprise content, records management, and policy pipelines. Discrepancies between development workstations, CI runners, lockfiles, and container deployments introduce runtime divergence risks.
- **Decision:** Standardize and pin Python 3.13 across all project configurations: `pyproject.toml` (`~=3.13.0`), GitHub Actions CI (`3.13`), `requirements.lock`, and architectural specifications. Python 3.13 provides key runtime improvements including optimized cyclic garbage collection, improved asyncio execution loop efficiency, improved error tracebacks, and full compatibility with our compiled C-extensions (`asyncpg`, `psycopg`, `cryptography`).
- **Consequences:** Eliminates interpreter version drift between local development, CI builds, and production deployments. All environments execute under identical language semantics.

## ADR 006: OCR Engine Architecture & Tesseract Installation Choice
- **Status:** Accepted
- **Context:** Automated full-text indexing, invoice extraction, and search capabilities require optical character recognition (OCR) across uploaded image formats and multi-page PDFs with fallback to scanned page rasterization.
- **Decision:** Utilize open-source Tesseract (via `pytesseract` 0.3.13) integrated with `pymupdf` (2.0) via asynchronous FastAPI BackgroundTasks. For Windows and WSL2 host environments, standardize on UB-Mannheim Tesseract-OCR (`C:\Program Files\Tesseract-OCR\tesseract.exe`) with a configurable `TESSERACT_CMD` environment variable, falling back gracefully to system PATH. PDFs utilize PyMuPDF direct text extraction for native digital text layers first; pages with sparse text (< 50 characters) are dynamically rasterized at 150 DPI and processed through Tesseract. Extracted text, page count, language, and confidence scores are persisted in a dedicated `document_text` table with PostgreSQL Row-Level Security (RLS).
- **Consequences:** Provides ultra-fast native Windows OCR performance without virtualization or network hop latency, robust fallback for scanned documents, and strict multi-tenant isolation in storage and search.

## ADR 007: OCR Engines Control Center, Multi-Tenant Dynamic Routing & Failover Architecture
- **Status:** Accepted
- **Context:** Modern enterprise document capture requires multiple specialized OCR engines (digital vector extraction, neural handwriting, Indic/multilingual scripts, low-contrast scans). Hardcoding a single engine leads to sub-optimal accuracy and single-point-of-failure risks.
- **Decision:** Implement a modular multi-engine architecture managed through an admin-facing "OCR Engines Control Center" with live status probing, dynamic tenant routing policies, Redis cache invalidation, and automated failover.
  - **PyMuPDF Engine (AGPL-3.0):** Native vector text layer extraction for born-digital PDFs (instant speed, 0% character error).
  - **Indra OCR Engine (MIT):** ONNX Transformer layout & OCR pipeline optimized for Indic scripts (Hindi/Devanagari) and complex tabular layouts.
  - **Tesseract Engine (Apache 2.0):** Production workhorse with adaptive OpenCV preprocessing (OSD, Hough deskew, CLAHE contrast gating, multi-pass PSM).
  - **Secondary & Optional Adapters:** PaddleOCR, docTR, EasyOCR, Surya, and Ollama Vision with graceful degradation and offline status reporting.
  - **Routing Policies:** Versioned policies stored in PostgreSQL with Row-Level Security (RLS) and Redis caching (`ocr_policy:{tenant_id}`). Supports one-click rollback.
- **Consequences:** Empowers tenants to optimize OCR speed and accuracy per document type while ensuring zero data loss and automated failover to Tesseract.


