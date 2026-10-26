# Elixir EIM - Threat Model (STRIDE)

## 1. Scope & Security Posture
Elixir EIM is a zero-trust multi-tenant system protecting confidential and classified enterprise documentation. Every operation must prove identity, tenant context, and explicit policy authorization.

## 2. STRIDE Threat Analysis

### Spoofing
- **Risk:** Stolen or forged JWT tokens, tenant impersonation.
- **Controls:** OIDC token validation against Keycloak/Entra ID; HttpOnly SameSite=Strict cookies; active session verification; tenant ID derived from verified identity claim, not user-supplied request parameters.

### Tampering
- **Risk:** Modification of document bytes, alteration of audit records, SQL injection.
- **Controls:** SHA-256 linear hash-chain on audit ledger; WORM / Object Lock on retention storage; SQLAlchemy 2 parameterized queries; strict MIME verification and magic-byte scanning.

### Repudiation
- **Risk:** An authorized user denies creating, approving, or deleting a document.
- **Controls:** Every decision (allowed or denied) is permanently logged with actor ID, IP, user-agent, timestamp, correlation ID, and chained cryptographic signature.

### Information Disclosure
- **Risk:** Cross-tenant leakage, search results revealing restricted document metadata, path traversal.
- **Controls:** PostgreSQL Row-Level Security (RLS) enforcement; permission-filtered search indexes; pre-signed S3 download URLs generated only after PEP verification.

### Denial of Service
- **Risk:** Malicious archive bombs, oversized document uploads, search resource exhaustion.
- **Controls:** Strict upload size caps and decompression limits; rate limiting per tenant and user; query complexity analysis.

### Elevation of Privilege
- **Risk:** Bypassing workflow approvals via direct REST API calls, IDOR vulnerabilities.
- **Controls:** PEP intercepts every protected endpoint; route-coverage CI test fails if any handler lacks PEP integration; workflow transitions require valid task execution tokens.
