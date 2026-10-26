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

### Unverified Items & Local Host Prerequisites
- **Local Docker Daemon:** Docker Desktop is currently **not installed** on this Windows host. Consequently, `docker compose up -d` and running containers locally could not be executed on the host machine.
- **Local PostgreSQL 16 Service:** Because Docker is not installed and no local Windows PostgreSQL service is running, live Alembic migrations against a local PostgreSQL server are currently unverified on this host machine (the database schema and RLS tests are fully automated and verified against the PostgreSQL 16 service container in CI).
