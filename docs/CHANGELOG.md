# Changelog

All notable changes to **Elixir Enterprise Information Management (Elixir EIM)** will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-dev] - 2026-10-26
### Added
- **feat(platform):** Monorepo structure, Docker Compose local infrastructure, and living documentation suite.
- **feat(platform):** Centralized `ProductBrandingConfig` single source of truth for all branding variables.
- **feat(platform):** Multi-tenant PostgreSQL RLS context and session propagation.
- **feat(platform):** Transactional Outbox event bus and resilient messaging models.
- **feat(platform):** Dynamic module manifest system (`module.yaml`) with dependency graph resolution.
- **feat(platform):** Feature flags with per-tenant toggle capabilities.
- **feat(cli):** `elixir-admin` enterprise management CLI skeleton.
- **feat(ci):** Strict GitHub Actions CI pipeline, ruff, mypy, pytest coverage, and import-linter boundary enforcement.
