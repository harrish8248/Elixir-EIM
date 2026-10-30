"""Tenant File Type Policy and Guardrails Resolution.

Evaluates detected file type and archive structure against tenant-specific database policies.
Three outcomes:
  - ALLOW: safe to proceed to scan & text extraction
  - QUARANTINE: file held in quarantine queue for administrative review
  - BLOCK: rejected immediately (e.g. executables, scripts, macro-enabled files, zip bombs)
"""

import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.content.intake.archive_inspector import ArchiveInspectionReport
from apps.api.app.content.intake.type_detector import TypeDetectionResult


class PolicyOutcome(str, Enum):
    ALLOW = "ALLOW"
    QUARANTINE = "QUARANTINE"
    BLOCK = "BLOCK"


@dataclass
class PolicyEvaluationResult:
    outcome: PolicyOutcome
    reason: str
    rule_matched: str
    is_blocked: bool
    is_quarantined: bool
    is_allowed: bool


# Non-negotiable global blocks (executables, scripts, macro office)
DEFAULT_BLOCK_EXTENSIONS: set[str] = {
    ".exe", ".dll", ".msi", ".bat", ".cmd", ".ps1", ".sh", ".js",
    ".vbs", ".jar", ".apk", ".com", ".scr", ".docm", ".xlsm", ".pptm",
}

DEFAULT_BLOCK_MIMES: set[str] = {
    "application/x-dosexec",
    "application/x-msdownload",
    "application/x-msi",
    "application/x-bat",
    "application/x-sh",
    "application/x-powershell",
    "text/javascript",
    "text/vbscript",
    "application/java-archive",
    "application/vnd.android.package-archive",
    "application/vnd.ms-word.document.macroEnabled.12",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
    "application/x-mach-binary",
    "application/x-elf",
}

DEFAULT_QUARANTINE_EXTENSIONS: set[str] = {
    ".iso", ".bin", ".dmg", ".pkg", ".7z", ".tar", ".gz",
}


@dataclass
class TenantGuardrailConfig:
    tenant_id: uuid.UUID
    max_upload_bytes: int = 52428800  # 50 MB
    allowed_types: list[str] = None  # type: ignore
    blocked_types: list[str] = None  # type: ignore
    quarantine_types: list[str] = None  # type: ignore
    archive_max_depth: int = 3
    archive_max_members: int = 500
    archive_max_ratio: float = 100.0
    clamav_enforce: bool = True
    strict_magic_bytes: bool = True
    min_clearance_restricted: int = 3
    sec17a4_mode: bool = False

    def __post_init__(self):
        if self.allowed_types is None:
            self.allowed_types = [
                "pdf", "png", "jpg", "jpeg", "docx", "xlsx", "pptx", "odt",
                "csv", "tsv", "txt", "json", "xml", "html", "md", "eml", "msg", "rtf", "zip"
            ]
        if self.blocked_types is None:
            self.blocked_types = [
                "exe", "dll", "msi", "bat", "cmd", "ps1", "sh", "js", "vbs",
                "jar", "apk", "com", "scr", "docm", "xlsm", "pptm"
            ]
        if self.quarantine_types is None:
            self.quarantine_types = ["iso", "bin", "dmg", "pkg", "7z", "tar", "gz"]


async def get_tenant_guardrail_config(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> TenantGuardrailConfig:
    """Fetch tenant guardrail policy from PostgreSQL or return default configuration."""
    try:
        res = await db.execute(
            text(
                """
                SELECT max_upload_bytes, allowed_types, blocked_types, quarantine_types,
                       archive_max_depth, archive_max_members, archive_max_ratio,
                       clamav_enforce, strict_magic_bytes, min_clearance_restricted, sec17a4_mode
                FROM tenant_guardrails
                WHERE tenant_id = :tenant_id
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
        row = res.fetchone()
        if row:
            return TenantGuardrailConfig(
                tenant_id=tenant_id,
                max_upload_bytes=row[0],
                allowed_types=row[1] if isinstance(row[1], list) else None,
                blocked_types=row[2] if isinstance(row[2], list) else None,
                quarantine_types=row[3] if isinstance(row[3], list) else None,
                archive_max_depth=row[4],
                archive_max_members=row[5],
                archive_max_ratio=float(row[6]),
                clamav_enforce=bool(row[7]),
                strict_magic_bytes=bool(row[8]),
                min_clearance_restricted=row[9],
                sec17a4_mode=bool(row[10]),
            )
    except Exception:
        pass

    return TenantGuardrailConfig(tenant_id=tenant_id)


def evaluate_type_policy(
    detected: TypeDetectionResult,
    archive_report: ArchiveInspectionReport | None,
    config: TenantGuardrailConfig,
    payload_size: int,
) -> PolicyEvaluationResult:
    """Evaluate detected type and optional archive report against tenant guardrail rules."""
    ext_clean = detected.extension.lstrip(".").lower()

    # 1. Payload size check
    if payload_size > config.max_upload_bytes:
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.BLOCK,
            reason=f"File size ({payload_size / (1024*1024):.1f} MB) exceeds maximum allowed limit ({config.max_upload_bytes / (1024*1024):.1f} MB)",
            rule_matched="MAX_SIZE_EXCEEDED",
            is_blocked=True,
            is_quarantined=False,
            is_allowed=False,
        )

    # 2. Strict executable / macro binary block
    if detected.is_executable or detected.mime_type in DEFAULT_BLOCK_MIMES or ext_clean in config.blocked_types:
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.BLOCK,
            reason=f"Executable binary or script content blocked by policy ({detected.description})",
            rule_matched="BLOCK_EXECUTABLE_OR_SCRIPT",
            is_blocked=True,
            is_quarantined=False,
            is_allowed=False,
        )

    if detected.is_macro_enabled or ext_clean in ("docm", "xlsm", "pptm"):
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.BLOCK,
            reason="Macro-enabled Microsoft Office document blocked by security policy",
            rule_matched="BLOCK_MACRO_ENABLED_OFFICE",
            is_blocked=True,
            is_quarantined=False,
            is_allowed=False,
        )

    # 3. Extension / Content spoofing check
    if config.strict_magic_bytes and detected.extension_mismatch:
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.BLOCK,
            reason=f"Extension/MIME mismatch detected: declared extension does not match magic bytes signature ({detected.mime_type})",
            rule_matched="EXTENSION_CONTENT_MISMATCH",
            is_blocked=True,
            is_quarantined=False,
            is_allowed=False,
        )

    # 4. Archive inspection violations (zip bomb, encrypted, dangerous members)
    if archive_report and not archive_report.is_safe:
        violations_str = "; ".join(archive_report.violations)
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.BLOCK,
            reason=f"Archive security inspection failed: {violations_str}",
            rule_matched="ARCHIVE_SECURITY_VIOLATION",
            is_blocked=True,
            is_quarantined=False,
            is_allowed=False,
        )

    # 5. Quarantine list check
    if ext_clean in config.quarantine_types:
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.QUARANTINE,
            reason=f"File type '{ext_clean}' designated for administrative quarantine review",
            rule_matched="TENANT_QUARANTINE_RULE",
            is_blocked=False,
            is_quarantined=True,
            is_allowed=False,
        )

    # 6. Allowed types check
    if ext_clean not in config.allowed_types:
        return PolicyEvaluationResult(
            outcome=PolicyOutcome.QUARANTINE,
            reason=f"Unrecognized file type '{ext_clean}' routed to quarantine queue",
            rule_matched="UNRECOGNIZED_TYPE_QUARANTINE",
            is_blocked=False,
            is_quarantined=True,
            is_allowed=False,
        )

    return PolicyEvaluationResult(
        outcome=PolicyOutcome.ALLOW,
        reason=f"File verified and allowed ({detected.description})",
        rule_matched="ALLOWED_BY_POLICY",
        is_blocked=False,
        is_quarantined=False,
        is_allowed=True,
    )

