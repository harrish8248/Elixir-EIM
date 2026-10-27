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
