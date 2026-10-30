# Elixir Enterprise Information Management — UX/UI Architecture & Design Notes

## Executive Overview
Elixir EIM is an enterprise-grade Information Management, Records Governance, and Intelligent Document Processing (IDP) suite. This document outlines the user experience architecture, design system tokens, heuristic foundations, and accessibility standards governing all modules.

---

## 1. Nielsen's Usability Heuristics & Architecture Implementation

### 1. Visibility of System Status
* **Universal Upload Pipeline**: Real-time progress feedback through each deterministic server stage:
  $$\text{Magic Bytes Check} \longrightarrow \text{ClamAV Scan} \longrightarrow \text{Sandboxed Extract} \longrightarrow \text{Sensitivity Classification} \longrightarrow \text{MinIO Hash Store}$$
* **Live System Badges**: Every UI view reflects real tenant database records and active OPA Rego policy clearance.
* **Fail-Closed Feedback**: When ClamAV or OPA encounters an exception or denial, immediate, high-visibility, plain-language error banners display exact correlation IDs and cryptographic ledger sequence numbers.

### 2. Match Between System and the Real World
* **Native Terminology**: Clear compliance labels grounded in ISO 15489, DoD 5015.02, and NIST 800-88 standards (e.g. *Legal Hold*, *Retention Schedule Code*, *Monotonic Cryptographic Chain*).
* **Side-by-Side Dual Pane Verification**: Split layout comparing the physical/spatial document invoice against extracted structured fields, reflecting the physical desk reviewer experience.

### 3. User Control and Freedom
* **Dirty State Tracking & Reversible Configuration**: Guardrails policy form alerts on unsaved changes, provides instant "Reset Changes" functionality, and prompts before discarding edits.
* **Administrative Quarantine Queue**: Quarantined items are never lost; administrators can inspect metadata, safely release them into permitted workspaces, or permanently purge them with confirmation modals.

### 4. Consistency and Standards
* **Design Tokens & Color Semantics**:
  - `Brand`: Deep Navy & Indigo palette (`#1E293B`, `#4F46E5`, `#6366F1`) signifying enterprise security and stability.
  - `Safe / Allowed`: Emerald (`#059669`, `#10B981`) for verified clean, public, and internal content.
  - `Sensitive / Warning`: Amber (`#D97706`, `#F59E0B`) for PII, PANs, GSTINs, and review queues.
  - `Critical / Error`: Rose & Ruby (`#DC2626`, `#EF4444`) for private keys, payment cards, Aadhaar, malware, and denials.
  - `Restricted Clearance`: Violet & Purple (`#7C3AED`, `#8B5CF6`) for Level 4 Restricted access.
* **Consistent Iconography**: Unified Lucide React icon family across all navigation bars, modals, tables, and badge components.

### 5. Error Prevention
* **Client & Stream Size Enforcement**: Dropzones calculate file size before stream initiation, preventing network overload for files exceeding the tenant maximum.
* **Immutable Guardrails**: Dangerous executable extensions (`.exe`, `.dll`, `.msi`, `.bat`, `.sh`) are non-negotiably blocked at the server level, preventing accidental misconfigurations by tenant admins.
* **Strict Fail-Closed Invariants**: ClamAV scanning cannot be bypassed or toggled off in production builds.

### 6. Recognition Rather than Recall
* **Explainability Chips**: Every sensitivity badge (`SAFE`, `SENSITIVE`, `CRITICAL`) features a click-to-expand chip revealing:
  - Exact matched algorithmic detectors (e.g. `aadhaar_verhoeff`, `luhn_card`, `aws_access_key`).
  - Masked redactions (e.g. `XXXX-XXXX-0019`, `AKIA************MPLE`).
  - Plain-language explanation for why the clearance was assigned.

### 7. Flexibility and Efficiency of Use
* **Multi-Format Ingestion**: Supports drag-and-drop or file browsing across 10+ formats (PDF, DOCX, XLSX, PPTX, ODT, CSV, JSON, HTML, EML, RTF, ZIP).
* **Keyboard Navigation & Global Shortcuts**: `Ctrl+K` global search shortcut, tab-index accessible forms, escape-key modal dismissals.

### 8. Aesthetic and Minimalist Design
* **Zero Hardcoded Mock Badges**: Removed all static fake strings, simulated progress bars, and unbacked compliance claims.
* **Progressive Disclosure**: High-density tables show core status at a glance, with expandable drawers for deep cryptographic provenance, audit trails, and bounding box coordinates.

### 9. Help Users Recognize, Diagnose, and Recover from Errors
* **Detailed 403 & 422 Errors**: Instead of generic failure toasts, access denials indicate:
  - The authenticated actor and email.
  - The actor's security clearance vs required document classification.
  - The exact OPA Rego rule and SHA-256 audit ledger entry.

### 10. Help and Documentation
* Clear contextual helper tooltips on all guardrail sliders, archive compression limits, and OCR routing rules.

---

## 2. Accessibility & WCAG 2.2 AA Conformance

* **Color Contrast**:
  - Normal text maintains a minimum contrast ratio of `4.5:1` against surrounding background surfaces.
  - Large headings and actionable badges maintain at least `3.0:1` contrast.
  - All status indicators combine color with text and icons (never relying on color alone).
* **Focus States**: High-contrast, 2px focus rings (`ring-2 ring-indigo-500 ring-offset-2`) on all interactive buttons, inputs, and toggles.
* **Screen Reader Semantic Markup**: Native `<button>`, `<input>`, `<dialog>`, and ARIA attributes (`aria-expanded`, `aria-label`, `role="status"`).

---

## 3. Component Architecture & Data Flow

```
[Universal Dropzone]
        │
        ▼
[POST /api/v1/content/intake/universal]
        │
   ┌────┴───────────────────────────────────────┐
   ▼                                            ▼
[HTTP 201 Created]                     [HTTP 202 Quarantined]
   │                                            │
[Result Card]                          [Quarantine Queue Tab]
 - True MIME & Content SHA-256          - Metadata Inspection
 - ClamAV Clean Verdict                 - Admin Release / Purge
 - Sensitivity Badge & Masked Chips     - Audited Diff
```

