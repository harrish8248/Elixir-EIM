# Elixir EIM 1.0 — Screen & Control Inventory

**Audit Timestamp:** 2026-10-28 10:35 UTC  
**Environment:** Active Docker Stack + FastAPI Backend (:8000) + Vite React Frontend (:5173)  
**Methodology:** Browser automated route walk-through, live control clicks, network API traffic inspection, and console log monitoring.

---

## 1. Core Feature Status Plain Statement

| Capability | Status Today | Real Evidence / Notes |
|---|---|---|
| **Keycloak Login (OIDC PKCE)** | **BROKEN** | Keycloak container port 8080 was unreachable during browser redirect (`ERR_CONNECTION_REFUSED`). |
| **Demo Session Login** | **WORKS** | Direct token exchange (`/api/v1/auth/token`) sets httpOnly session cookie and logs in as Sarah, Raj, Maria, or Auditor. |
| **Document Upload** | **WORKS** | Multipart form upload to MinIO S3 bucket `elixir-eim-content` via `POST /api/v1/content/documents`. |
| **ClamAV Antivirus Scan** | **WORKS** | Clean files pass stream scan in `apps/api/app/content/router.py`. |
| **EICAR Malware Block** | **WORKS** | EICAR signature is detected by ClamAV, blocked with 422, and quarantined. |
| **OCR (Tesseract / PyMuPDF)** | **MISSING** | Not implemented yet (scheduled for Step 3). |
| **Search (PostgreSQL Full-Text)**| **MOCK / PARTIAL** | Basic `ILIKE` title search exists; PostgreSQL `tsvector + GIN`, OCR text indexing, snippets, and facets are not built yet. |
| **Permission-Safe Search** | **BROKEN / MISSING**| Maria (HR) can currently see documents belonging to Finance in search results because SQL lacks clearance/department filtering. |
| **Audit Hash Chain Verify** | **WORKS** | `GET /api/v1/audit/verify` re-computes SHA-256 chain across all blocks and returns `VALID`. |
| **Legal Hold Enforcement** | **BROKEN** | Legal hold record can be created, but deletion prevention on held records is not enforced on the backend. |
| **Approvals / Self-Approval Block**| **BROKEN** | Task approval works, but dual-control self-approval prevention is not enforced in the workflow engine. |

---

## 2. Screen-by-Screen Control Inventory

### Screen: Authentication (`/login`)
| Control / Action | State | Notes |
|---|---|---|
| "Authenticate with Keycloak (OIDC)" | BROKEN | Redirects to `http://localhost:8080/realms/elixir/protocol/openid-connect/auth` which failed with connection refused. |
| Username / Password fields | NO-OP | Keycloak direct grant submission is unhooked without active Keycloak. |
| "Demo: Sarah Chen (Records Manager)" | WORKS | Issues session cookie for `sarah.chen@acrocorp.com` (Finance dept, Level 4). |
| "Demo: Raj Patel (Employee)" | WORKS | Issues session cookie for `raj.patel@acrocorp.com` (Finance dept, Level 2). |
| "Demo: Maria Garcia (HR)" | WORKS | Issues session cookie for `maria.garcia@acrocorp.com` (HR dept, Level 2). |
| "Demo: Marcus Vance (Auditor)" | WORKS | Issues session cookie for `marcus.vance@acrocorp.com` (Compliance, Level 3). |
| Dark / Light Theme Toggle | WORKS | Toggles `dark` class on root HTML element and persists state. |

---

### Screen: Content Explorer (`/content`)
| Control / Action | State | Notes |
|---|---|---|
| Folder Navigation Tree | WORKS | Populates folders dynamically from `/api/v1/content/folders`. |
| Breadcrumb Navigation | WORKS | Updates path and allows clicking parent directories. |
| "New Folder" Button | WORKS | Opens modal and creates folder via `POST /api/v1/content/folders`. |
| "Upload Document" Button | WORKS | Opens file selector modal, streams file to MinIO, and creates document record. |
| Document Row Click | WORKS | Opens side slide-out drawer with details. |
| "Download" Button | WORKS | Generates presigned MinIO URL and triggers file download. |
| "View Versions" Button | WORKS | Lists all historic versions with sha256 checksums. |
| "Check Out" Button | WORKS | Locks document to current user ID. |
| "Check In" Button | WORKS | Releases lock and optionally creates new version. |
| "Delete Document" Button | BROKEN | Deletes document without checking for active legal holds. |
| OCR Tab in Document Drawer | MISSING | Drawer does not yet have an OCR text viewer or confidence score. |

---

### Screen: Records & Retention (`/records`)
| Control / Action | State | Notes |
|---|---|---|
| Schedules Tab | WORKS | Loads retention schedules from `/api/v1/records/schedules`. |
| "Create Schedule" Button | WORKS | Modal form creates schedule with trigger event and retention years. |
| Legal Holds Tab | WORKS | Displays active legal holds from `/api/v1/records/holds`. |
| "Create Legal Hold" Button | WORKS | Creates legal hold with case number, reason, and custodian. |
| "Declare Record" Action | WORKS | Flags document as an official record via `/api/v1/records/declare`. |
| "Lift Hold" Button | WORKS | Lifts hold via `/api/v1/records/holds/{id}/lift`. |
| Deletion Prevention Enforcement | BROKEN | No backend guard blocks DELETE on held records. |

---

### Screen: Workflows & Approvals (`/workflow`)
| Control / Action | State | Notes |
|---|---|---|
| Tasks Inbox List | WORKS | Displays assigned tasks from `/api/v1/workflow/tasks`. |
| "Launch Workflow" Button | WORKS | Starts review workflow instance. |
| "Approve" Task Button | WORKS | Advances workflow instance state. |
| "Reject" Task Button | WORKS | Terminates workflow instance with rejection note. |
| Self-Approval Prevention | BROKEN | An initiator can approve their own request; must be blocked and audited. |

---

### Screen: Enterprise Search (`/search`)
| Control / Action | State | Notes |
|---|---|---|
| Search Query Input | WORKS | Triggers search request to backend. |
| Search Typeahead / Submit | WORKS | Returns matching documents. |
| PostgreSQL Full-Text (tsvector + GIN) | MOCK | Uses simple ILIKE search rather than full-text index on OCR and content. |
| Permission-Safe Filtering | BROKEN | Department and clearance checks are missing in SQL queries. |
| Faceted Filters (Department, Type) | NO-OP | UI filters do not dynamically aggregate SQL facets. |
| Text Snippet Highlighting | MISSING | Does not return matching text snippets with highlighted keywords. |

---

### Screen: Trust Layer & Governance (`/governance`)
| Control / Action | State | Notes |
|---|---|---|
| Audit Events Table | WORKS | Live streaming list from `/api/v1/audit/events`. |
| "Verify Hash Chain Integrity" | WORKS | Computes SHA-256 chain verification against `/api/v1/audit/verify`. |
| Tenant Filter Dropdown | WORKS | Filters events by tenant ID. |
| "Export Audit Report" | NO-OP | Button clicks with no download action. |

---

### Screen: Administration Console (`/admin`)
| Control / Action | State | Notes |
|---|---|---|
| Users List | WORKS | Lists tenant users with roles and clearance levels. |
| "Invite / Add User" Button | NO-OP | Modal appears but submit is disabled or not hooked to SCIM/API. |
| System Status Cards | WORKS | Shows status of Postgres, Redis, MinIO, OPA, ClamAV, Keycloak. |
| Maintenance Mode Toggle | NO-OP | Switch toggles locally in state, no backend maintenance mode set. |
