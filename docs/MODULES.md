# Elixir EIM - Module Registry & Specifications

Every module within Elixir EIM contains a `module.yaml` manifest that defines its version, dependencies, permissions, published/consumed events, configuration schema, and UI routes.

## Registered Modules

### Layer 0: Platform Foundation
- **`platform`**: Platform configuration, branding single source of truth, error handling, correlation IDs, outbox events, feature flags, and module registry.

### Layer 1: Tenancy & Identity
- **`tenancy`**: Multi-tenant context management, RLS session variable propagation, tenant isolation.
- **`identity`**: OIDC authentication, SCIM 2.0 provisioning, RBAC/ABAC models, session validation.

### Layer 2 & 3: Trust Layer
- **`pdp`**: Policy Decision Point evaluating OPA Rego rules against RBAC and ABAC attributes.
- **`guardrails`**: Input validation, magic-byte inspection, archive decompression guards, ClamAV anti-malware pipeline.
- **`audit`**: SHA-256 linear hash-chained immutable audit ledger.
- **`pep`**: Policy Enforcement Point intercepting requests before reaching domain routers.

### Layer 4: Business Domains
- **`content`**: Enterprise workspaces, folders, documents, versioning, renditions, trash, and sharing.
- **`records`**: File plans, retention schedules, disposition queues, and legal holds.
- **`workflow`**: State machine process automation engine, task inbox, SLA management, and dynamic forms.
- **`search`**: Provider abstraction with PostgreSQL FTS implementation and permission filtering.
- **`admin`**: Tenant management, user directory, content types designer, feature toggles, and system settings.
- **`integrations`**: Public REST API, API key credentials, and transactional webhooks.

### Layer 5: Extensions & Future Release Skeletons
- **`extensions`**: Plugin SDK and dynamic extension loader.
- **`capture`** *(1.1 Skeleton)*: Intelligent Document Processing and OCR.
- **`cases`** *(1.2 Skeleton)*: Dynamic case management.
- **`ai`** *(1.4 Skeleton)*: Guardrailed AI Assistant.
- **`analytics`** *(1.5 Skeleton)*: Audit and operational reporting engine.
