"""Explainable Local Sensitivity Classifier and Entity Detection Engine.

Labels:
  - SAFE: Public / Standard internal operational content (Mapped clearance: PUBLIC / INTERNAL)
  - SENSITIVE: Personal data, payroll, taxes, employee identifiers (Mapped clearance: CONFIDENTIAL)
  - CRITICAL: Regulated financial cards, Aadhaar, private keys, cloud tokens (Mapped clearance: RESTRICTED)
  - UNCLASSIFIED: Content has no extractable text (Media, audio, CAD, encrypted). Never labelled SAFE.

100% offline, local, deterministic, and explainable with zero external APIs or LLMs.
All detected sensitive entities are masked in findings (e.g. XXXX-XXXX-1234).
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from apps.api.app.content.idp.gstin import validate_gstin
from apps.api.app.content.intake.luhn import validate_luhn
from apps.api.app.content.intake.verhoeff import validate_aadhaar


class SensitivityLabel(str, Enum):
    SAFE = "SAFE"
    SENSITIVE = "SENSITIVE"
    CRITICAL = "CRITICAL"
    UNCLASSIFIED = "UNCLASSIFIED"


CLEARANCE_MAP: dict[SensitivityLabel, str] = {
    SensitivityLabel.SAFE: "INTERNAL",
    SensitivityLabel.SENSITIVE: "CONFIDENTIAL",
    SensitivityLabel.CRITICAL: "RESTRICTED",
    SensitivityLabel.UNCLASSIFIED: "INTERNAL",
}


@dataclass
class FindingDetail:
    detector: str
    category: str  # id, financial, secret, personal, context
    count: int
    masked_examples: list[str] = field(default_factory=list)
    locations: list[int] = field(default_factory=list)  # character offsets


@dataclass
class ClassificationReport:
    label: SensitivityLabel
    mapped_clearance: str
    confidence: float
    summary_reason: str
    findings: list[FindingDetail] = field(default_factory=list)
    total_detections: int = 0
    can_auto_approve: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Masking Helpers
# ---------------------------------------------------------------------------

def mask_aadhaar(val: str) -> str:
    clean = "".join(c for c in val if c.isdigit())
    if len(clean) == 12:
        return f"XXXX-XXXX-{clean[-4:]}"
    return "XXXX-XXXX-XXXX"


def mask_card(val: str) -> str:
    clean = "".join(c for c in val if c.isdigit())
    if len(clean) >= 4:
        return f"XXXX-XXXX-XXXX-{clean[-4:]}"
    return "XXXX-XXXX-XXXX"


def mask_pan(val: str) -> str:
    clean = val.strip().upper()
    if len(clean) == 10:
        return f"XXXXX{clean[5:9]}X"
    return "XXXXXXXXXX"


def mask_gstin(val: str) -> str:
    clean = val.strip().upper()
    if len(clean) == 15:
        return f"{clean[:2]}XXXXXXX{clean[9:13]}XX"
    return "XXXXXXXXXXXXXXX"


def mask_email(val: str) -> str:
    parts = val.split("@")
    if len(parts) == 2:
        user, domain = parts
        masked_user = user[0] + "***" if user else "***"
        return f"{masked_user}@{domain}"
    return "***@***.***"


def mask_token(val: str) -> str:
    if len(val) > 8:
        return f"{val[:4]}{'*' * (len(val) - 8)}{val[-4:]}"
    return "********"


# ---------------------------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------------------------

PAN_REGEX = re.compile(r"\b([A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z])\b")
AADHAAR_REGEX = re.compile(r"\b([2-9][0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4})\b")
GSTIN_REGEX = re.compile(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}[Z]{1}[0-9A-Z]{1})\b")
IFSC_REGEX = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
INDIAN_MOBILE_REGEX = re.compile(r"(?:phone|mobile|cell|contact|tel|call)(?:[\s\w]{0,15})?[:.-]?\s*(\+?91[\s.-]?)?([6-9][0-9]{9})\b", re.IGNORECASE)
CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b|\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b|\b\d{13,19}\b")
PEM_KEY_REGEX = re.compile(r"-----BEGIN (?:[A-Z0-9\s]+ )?PRIVATE KEY-----")
AWS_KEY_REGEX = re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
GITHUB_TOKEN_REGEX = re.compile(r"\b(ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82})\b")
SLACK_TOKEN_REGEX = re.compile(r"\b(xox[baprs]-[0-9a-zA-Z-]{10,80}|xapp-[0-9a-zA-Z-]{10,80})\b")
JWT_TOKEN_REGEX = re.compile(r"\b(eyJ[A-Za-z0-9-_=]{15,}\.eyJ[A-Za-z0-9-_=]{15,}\.[A-Za-z0-9-_.+/=]{15,})\b")
PASSWORD_CONFIG_REGEX = re.compile(r"(?:password|passwd|secret_key|api_key|api_secret|auth_token)\s*[:=]\s*['\"]([^'\"]{6,})['\"]", re.IGNORECASE)
EMAIL_PERSONAL_REGEX = re.compile(r"\b([a-zA-Z0-9_.+-]+@(?:gmail|yahoo|hotmail|outlook|proton|icloud)\.[a-zA-Z0-9-.]+)\b", re.IGNORECASE)
CONTEXT_ADDRESS_REGEX = re.compile(r"(?:address|flat|plot|residence|layout|street)[\s\w,.-]*\b([1-9][0-9]{5})\b", re.IGNORECASE)

CONTEXT_SALARY_REGEX = re.compile(r"\b(salary|payroll|compensation|gross pay|net pay|remuneration|ctc breakdown|annual ctc)\b", re.IGNORECASE)
CONTEXT_MEDICAL_REGEX = re.compile(r"\b(diagnosis|patient id|prescription|hospital admission|medical report|medical assessment|medical record|clinical history)\b", re.IGNORECASE)
CONTEXT_NDA_REGEX = re.compile(r"\b(non-disclosure agreement|confidentiality agreement|trade secret|proprietary information|strictly confidential)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Classification Logic
# ---------------------------------------------------------------------------

def classify_text(text: str | None) -> ClassificationReport:
    """Evaluate text content against algorithmic detectors and return explainable sensitivity report."""
    if not text or not text.strip():
        return ClassificationReport(
            label=SensitivityLabel.UNCLASSIFIED,
            mapped_clearance="INTERNAL",
            confidence=1.0,
            summary_reason="Not classified: no text extracted from content",
            findings=[],
            total_detections=0,
            can_auto_approve=False,
            metadata={"text_length": 0},
        )

    findings: list[FindingDetail] = []
    is_critical = False
    is_sensitive = False
    critical_reasons: list[str] = []
    sensitive_reasons: list[str] = []

    # 1. CRITICAL DETECTORS: Private Keys & Tokens
    pem_matches = list(PEM_KEY_REGEX.finditer(text))
    if pem_matches:
        is_critical = True
        critical_reasons.append(f"{len(pem_matches)} Cryptographic Private Key(s)")
        findings.append(FindingDetail(
            detector="pem_private_key",
            category="secret",
            count=len(pem_matches),
            masked_examples=["-----BEGIN PRIVATE KEY...[REDACTED]-----"],
            locations=[m.start() for m in pem_matches],
        ))

    aws_matches = list(AWS_KEY_REGEX.finditer(text))
    if aws_matches:
        is_critical = True
        critical_reasons.append(f"{len(aws_matches)} AWS Access Key(s)")
        findings.append(FindingDetail(
            detector="aws_access_key",
            category="secret",
            count=len(aws_matches),
            masked_examples=[mask_token(m.group(1)) for m in aws_matches[:3]],
            locations=[m.start() for m in aws_matches],
        ))

    github_matches = list(GITHUB_TOKEN_REGEX.finditer(text))
    if github_matches:
        is_critical = True
        critical_reasons.append(f"{len(github_matches)} GitHub Personal Access Token(s)")
        findings.append(FindingDetail(
            detector="github_token",
            category="secret",
            count=len(github_matches),
            masked_examples=[mask_token(m.group(1)) for m in github_matches[:3]],
            locations=[m.start() for m in github_matches],
        ))

    jwt_matches = list(JWT_TOKEN_REGEX.finditer(text))
    if jwt_matches:
        is_critical = True
        critical_reasons.append(f"{len(jwt_matches)} JSON Web Token (JWT)")
        findings.append(FindingDetail(
            detector="jwt_token",
            category="secret",
            count=len(jwt_matches),
            masked_examples=[mask_token(m.group(1)) for m in jwt_matches[:3]],
            locations=[m.start() for m in jwt_matches],
        ))

    pwd_matches = list(PASSWORD_CONFIG_REGEX.finditer(text))
    if pwd_matches:
        is_critical = True
        critical_reasons.append(f"{len(pwd_matches)} Hardcoded Credential / Secret Key(s)")
        findings.append(FindingDetail(
            detector="hardcoded_credential",
            category="secret",
            count=len(pwd_matches),
            masked_examples=["password=********"],
            locations=[m.start() for m in pwd_matches],
        ))

    # 2. CRITICAL DETECTOR: Payment Cards (Validated with Luhn)
    valid_cards: list[tuple[str, int]] = []
    for m in CARD_REGEX.finditer(text):
        raw_card = m.group(0)
        digits = "".join(c for c in raw_card if c.isdigit())
        if 13 <= len(digits) <= 19 and validate_luhn(digits):
            valid_cards.append((digits, m.start()))

    if valid_cards:
        is_critical = True
        critical_reasons.append(f"{len(valid_cards)} Valid Payment Card Number(s) (Luhn Verified)")
        findings.append(FindingDetail(
            detector="payment_card_luhn",
            category="financial",
            count=len(valid_cards),
            masked_examples=[mask_card(c[0]) for c in valid_cards[:3]],
            locations=[c[1] for c in valid_cards],
        ))

    # 3. CRITICAL DETECTOR: Aadhaar Numbers (Validated with Verhoeff)
    valid_aadhaars: list[tuple[str, int]] = []
    for m in AADHAAR_REGEX.finditer(text):
        candidate = "".join(c for c in m.group(1) if c.isdigit())
        if len(candidate) == 12 and validate_aadhaar(candidate):
            valid_aadhaars.append((candidate, m.start()))

    if valid_aadhaars:
        is_critical = True
        critical_reasons.append(f"{len(valid_aadhaars)} Valid Indian Aadhaar Number(s) (Verhoeff Verified)")
        findings.append(FindingDetail(
            detector="aadhaar_verhoeff",
            category="id",
            count=len(valid_aadhaars),
            masked_examples=[mask_aadhaar(a[0]) for a in valid_aadhaars[:3]],
            locations=[a[1] for a in valid_aadhaars],
        ))

    # 4. SENSITIVE DETECTOR: Indian PAN Numbers
    pan_matches = list(PAN_REGEX.finditer(text))
    if pan_matches:
        is_sensitive = True
        sensitive_reasons.append(f"{len(pan_matches)} Indian PAN Number(s)")
        findings.append(FindingDetail(
            detector="pan_number",
            category="id",
            count=len(pan_matches),
            masked_examples=[mask_pan(m.group(1)) for m in pan_matches[:3]],
            locations=[m.start() for m in pan_matches],
        ))

    # 5. SENSITIVE DETECTOR: GSTIN (Validated with Mod-36)
    valid_gstins: list[tuple[str, int]] = []
    for m in GSTIN_REGEX.finditer(text):
        cand = m.group(1)
        is_valid, _ = validate_gstin(cand)
        if is_valid:
            valid_gstins.append((cand, m.start()))

    if valid_gstins:
        is_sensitive = True
        sensitive_reasons.append(f"{len(valid_gstins)} Verified Indian GSTIN(s)")
        findings.append(FindingDetail(
            detector="gstin_mod36",
            category="id",
            count=len(valid_gstins),
            masked_examples=[mask_gstin(g[0]) for g in valid_gstins[:3]],
            locations=[g[1] for g in valid_gstins],
        ))

    # 6. SENSITIVE DETECTOR: Indian Mobile Numbers with Context
    mob_matches = list(INDIAN_MOBILE_REGEX.finditer(text))
    if mob_matches:
        is_sensitive = True
        sensitive_reasons.append(f"{len(mob_matches)} Indian Mobile Number(s)")
        findings.append(FindingDetail(
            detector="indian_mobile",
            category="personal",
            count=len(mob_matches),
            masked_examples=[f"XXXXX-{m.group(2)[-4:]}" for m in mob_matches[:3]],
            locations=[m.start() for m in mob_matches],
        ))

    # 7. SENSITIVE DETECTOR: IFSC Bank Code
    ifsc_matches = list(IFSC_REGEX.finditer(text))
    if ifsc_matches:
        is_sensitive = True
        sensitive_reasons.append(f"{len(ifsc_matches)} Indian IFSC Code(s)")
        findings.append(FindingDetail(
            detector="ifsc_code",
            category="financial",
            count=len(ifsc_matches),
            masked_examples=[m.group(1) for m in ifsc_matches[:3]],
            locations=[m.start() for m in ifsc_matches],
        ))

    # 8. SENSITIVE DETECTOR: Context Keywords (Salary / Medical / NDA)
    salary_matches = list(CONTEXT_SALARY_REGEX.finditer(text))
    if salary_matches:
        is_sensitive = True
        sensitive_reasons.append("Payroll & Executive Compensation Data")
        findings.append(FindingDetail(
            detector="salary_payroll_keywords",
            category="context",
            count=len(salary_matches),
            masked_examples=[m.group(1).lower() for m in salary_matches[:3]],
            locations=[m.start() for m in salary_matches],
        ))

    medical_matches = list(CONTEXT_MEDICAL_REGEX.finditer(text))
    if medical_matches:
        is_sensitive = True
        sensitive_reasons.append("Protected Health & Clinical Diagnostic Data")
        findings.append(FindingDetail(
            detector="medical_diagnostic_keywords",
            category="context",
            count=len(medical_matches),
            masked_examples=[m.group(1).lower() for m in medical_matches[:3]],
            locations=[m.start() for m in medical_matches],
        ))

    nda_matches = list(CONTEXT_NDA_REGEX.finditer(text))
    if nda_matches:
        is_sensitive = True
        sensitive_reasons.append("Confidentiality / NDA Legal Agreement")
        findings.append(FindingDetail(
            detector="confidential_nda_keywords",
            category="context",
            count=len(nda_matches),
            masked_examples=[m.group(1).lower() for m in nda_matches[:3]],
            locations=[m.start() for m in nda_matches],
        ))

    email_matches = list(EMAIL_PERSONAL_REGEX.finditer(text))
    if email_matches:
        is_sensitive = True
        sensitive_reasons.append(f"{len(email_matches)} Personal Webmail Address(es)")
        findings.append(FindingDetail(
            detector="personal_email",
            category="personal",
            count=len(email_matches),
            masked_examples=[mask_email(m.group(1)) for m in email_matches[:3]],
            locations=[m.start() for m in email_matches],
        ))

    address_matches = list(CONTEXT_ADDRESS_REGEX.finditer(text))
    if address_matches:
        is_sensitive = True
        sensitive_reasons.append("Residential Address with Postal PIN")
        findings.append(FindingDetail(
            detector="residential_address",
            category="personal",
            count=len(address_matches),
            masked_examples=[f"PIN: {m.group(1)}" for m in address_matches[:3]],
            locations=[m.start() for m in address_matches],
        ))

    total_detections = sum(f.count for f in findings)

    # Resolve Final Label & Reason
    if is_critical:
        label = SensitivityLabel.CRITICAL
        mapped = CLEARANCE_MAP[label]
        summary = f"CRITICAL: Contains {'; '.join(critical_reasons)}"
    elif is_sensitive:
        label = SensitivityLabel.SENSITIVE
        mapped = CLEARANCE_MAP[label]
        summary = f"SENSITIVE: Contains {'; '.join(sensitive_reasons)}"
    else:
        label = SensitivityLabel.SAFE
        mapped = CLEARANCE_MAP[label]
        summary = "SAFE: No regulated identifiers, payment cards, or secrets detected"

    return ClassificationReport(
        label=label,
        mapped_clearance=mapped,
        confidence=0.99 if findings else 0.95,
        summary_reason=summary,
        findings=findings,
        total_detections=total_detections,
        can_auto_approve=label == SensitivityLabel.SAFE,
        metadata={"text_length": len(text)},
    )
