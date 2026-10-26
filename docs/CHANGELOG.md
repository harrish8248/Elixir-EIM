# Changelog

All notable changes to **Elixir Enterprise Information Management (Elixir EIM)** will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-dev] - 2026-10-26 (Phase 1 Closeout)
### Added
- **feat(platform):** Monorepo structure, Docker Compose local infrastructure, and living documentation suite.
- **feat(platform):** Centralized `ProductBrandingConfig` single source of truth for all branding variables in `platform.branding` and `branding.ts`.
- **feat(platform):** Multi-tenant PostgreSQL RLS context, session propagation, and non-superuser application role tests (`test_rls_postgres.py`).
- **feat(platform):** Transactional Outbox event bus and resilient messaging models (`OutboxEvent`).
- **feat(platform):** Dynamic module manifest system (`module.yaml`) with Kahn's algorithm topological DAG resolution.
- **feat(platform):** Feature flags with per-tenant toggle capabilities.
- **feat(cli):** `elixir-admin` enterprise management CLI skeleton with `check-upgrade`, `migrate`, `verify-audit-chain`, `seed-demo`.
- **feat(ci):** Strict GitHub Actions CI pipeline, ruff, mypy, pytest coverage, import-linter boundary enforcement, and Dependabot automation.
- **feat(ci):** Committed pinned Python reproducible lockfile (`requirements.lock`).
- **feat(web):** Enterprise React 18 frontend shell with calm institutional palette, WCAG 2.2 AA design tokens, 4px grid, and dark mode toggle.
- **feat(web):** Verified Storybook component build (`storybook build`) with Button and StatusPill stories.
- **feat(web):** Interactive Content Explorer, Records & Retention Management, and Elixir Trust Layer Dashboard views.
### Verified Live Infrastructure & Services
- **Infrastructure (Docker Compose):** All 7 services live, running, and healthy: PostgreSQL 16 Alpine, Redis 7 Alpine, MinIO, Keycloak 26.0, OPA latest, ClamAV 1.4, Gotenberg 8.12.
- **Database Migrations:** Alembic migrations applied live against real PostgreSQL 16 container (`0001_platform_foundation`). Verified tables: `alembic_version`, `audit_events`, `feature_flags`, `outbox_events`, `tenant_feature_flags`, `tenants`.
- **PostgreSQL Row-Level Security:** Verified against real PostgreSQL with non-superuser role `elixir_app_role` (`usesuper=False`, `rolbypassrls=False`). Proved cross-tenant isolation, 0 rows returned without tenant context, and RLS WITH CHECK violation when inserting into other tenants.
- **Identity & Access Management:** Verified Keycloak 26 `elixir` realm import with all 8 roles and 3 users (`admin@elixir.internal`, `john.doe@acrocorp.com`, `sarah.chen@acrocorp.com`).
- **Policy Engine (OPA):** Verified OPA health endpoint and live policy evaluation (`authz/allow`) with test claims.
- **Malware Scanner (ClamAV):** Verified ClamAV daemon readiness, ping/pong, clean stream scanning, and live EICAR virus signature detection (`stream: Eicar-Test-Signature FOUND`).
- **Code Quality & Test Suites:** Full test suite passing (16/16 pytest with 86% coverage, 2/2 import-linter contracts kept, ruff clean, mypy clean with 0 issues in 33 files, web typecheck clean, Vitest 3/3 passed, Vite build succeeded).
