# Elixir Enterprise Information Management (Elixir EIM) - Architecture

## 1. Overview
Elixir EIM is a production-grade, multi-tenant enterprise information management suite built as a modular monolith. It provides content services, records management, process automation, permission-filtered search, administrative governance, and guardrailed extensions.

## 2. Core Architectural Principles
- **Deny By Default:** All routes pass through the Policy Enforcement Point (PEP). Requests without an explicit `ALLOW` from the Policy Decision Point (PDP) are rejected.
- **Cross-Cutting Trust Layer:** The Trust Layer (PEP, PDP, Guardrails, Immutable Audit) intercepts operations across all modules.
- **Multi-Tenancy with RLS:** Every table has a `tenant_id` foreign key and is protected by PostgreSQL 16 Row-Level Security (RLS) policies.
- **Strict Boundary Separation:** Domain modules (`content`, `records`, `workflow`, `search`, `admin`, `integrations`) never query each other's database tables or import internal services directly. They communicate exclusively through public contract interfaces and transactional outbox events.
- **Expand / Contract Database Evolution:** Zero-downtime, rollback-safe schema migrations.
- **Unified Branding Source:** The product name ("Elixir Enterprise Information Management"), short name ("Elixir EIM"), version, and corporate branding are defined in `platform.branding` and cannot be hardcoded.

## 3. Tier Topology
1. **Frontend:** React 18 SPA (`apps/web`) using TypeScript, Tailwind CSS, Radix UI, TanStack Query, React Flow, and PDF.js.
2. **API & Engine:** FastAPI application (`apps/api/app`) running on Python 3.13 with SQLAlchemy 2 (async).
3. **Data Tier:** PostgreSQL 16 (app data, full-text search, RLS), Redis 7 (caching, locking, queues), MinIO/S3 (content blobs and WORM storage).
4. **Processing & Security:** ClamAV (malware scanning), Gotenberg (PDF/A rendition conversion), Open Policy Agent (Rego rules).
