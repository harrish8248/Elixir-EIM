"""
Business Validation Rules Engine for Elixir EIM IDP (Vendor Invoice Management).
Performs:
1. Subtotal + Tax = Total math reconciliation
2. Line items sum = Subtotal math reconciliation
3. Required fields completeness check
4. Date sanity check (invoice_date <= today, due_date >= invoice_date)
5. Duplicate invoice check (vendor + invoice_number + total)
6. Purchase Order matching (PO number, vendor match, price/quantity check)
7. Vendor Master Catalog verification
8. Configurable confidence thresholds and STP (Straight-Through Processing) determination
"""

from datetime import date, datetime
from typing import Any
import uuid

from apps.api.app.content.idp.models import ExtractedField, JobStatus, LineItem, ValidationRuleResult, ValidationSummary
from apps.api.app.platform.logging import logger

# Seeded Purchase Orders catalog for PO matching
SEEDED_PURCHASE_ORDERS = {
    "PO-2026-7000": {"vendor": "CloudScale Networks Inc", "total": 6089.00, "status": "open"},
    "PO-2026-7001": {"vendor": "Apex Cloud Infrastructure Inc", "total": 12500.00, "status": "open"},
    "PO-2026-7002": {"vendor": "Vertex Data Solutions Ltd", "total": 4200.00, "status": "open"},
    "PO-2026-7003": {"vendor": "Nexus AI Research Labs", "total": 8900.00, "status": "open"},
    "PO-2026-7004": {"vendor": "Sentinel Security Operations", "total": 5400.00, "status": "open"},
    "PO-2026-7005": {"vendor": "Horizon Legal Partners LLP", "total": 3500.00, "status": "open"},
}

SEEDED_VENDOR_MASTER = {
    "Apex Cloud Infrastructure Inc": {"tax_id": "US-84-1928471", "status": "approved", "payment_terms": "Net 30"},
    "Vertex Data Solutions Ltd": {"tax_id": "GB-992-81726", "status": "approved", "payment_terms": "Net 30"},
    "Nexus AI Research Labs": {"tax_id": "US-47-2819034", "status": "approved", "payment_terms": "Net 45"},
    "Pinnacle Software Systems": {"tax_id": "US-22-9481729", "status": "approved", "payment_terms": "Net 30"},
    "Optima Logistics & Freight": {"tax_id": "US-33-8172645", "status": "approved", "payment_terms": "Net 30"},
    "Stratis IT Consulting Group": {"tax_id": "US-55-1928374", "status": "approved", "payment_terms": "Net 30"},
    "Global Enterprise Hardware Corp": {"tax_id": "US-11-2837465", "status": "approved", "payment_terms": "Net 60"},
    "Quantum Cybersecurity Partners": {"tax_id": "US-99-3847561", "status": "approved", "payment_terms": "Net 30"},
    "CloudScale Networks Inc": {"tax_id": "US-77-4839201", "status": "approved", "payment_terms": "Net 30"},
    "Horizon Legal Partners LLP": {"tax_id": "US-66-5948372", "status": "approved", "payment_terms": "Net 30"},
    "Sentinel Security Operations": {"tax_id": "US-33-6849302", "status": "approved", "payment_terms": "Net 30"},
    "AcroCorp Global Operations": {"tax_id": "US-12-3456789", "status": "approved", "payment_terms": "Net 30"},
    "Partner Services Group Inc": {"tax_id": "US-44-8392019", "status": "approved", "payment_terms": "Net 30"},
}


class ValidationEngine:
    """Validates extracted invoice data and determines STP auto-approval status."""

    def __init__(
        self,
        confidence_threshold: float = 0.85,
        math_tolerance: float = 0.05,
        existing_invoices: set[tuple[str, str, float]] | None = None,
        vendor_master: dict[str, Any] | None = None,
        purchase_orders: dict[str, Any] | None = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.math_tolerance = math_tolerance
        self.existing_invoices = existing_invoices if existing_invoices is not None else set()
        self.vendor_master = vendor_master or SEEDED_VENDOR_MASTER
        self.purchase_orders = purchase_orders or SEEDED_PURCHASE_ORDERS

    def validate(
        self,
        fields: dict[str, ExtractedField],
        line_items: list[LineItem],
        tenant_config: dict[str, Any] | None = None,
    ) -> ValidationSummary:
        """Execute all validation rules and return summary."""
        cfg = tenant_config or {}
        conf_thresh = cfg.get("confidence_threshold", self.confidence_threshold)
        tolerance = cfg.get("math_tolerance", self.math_tolerance)

        rules: list[ValidationRuleResult] = []
        reasons: list[str] = []

        # 1. Required Fields Check
        required_keys = ["vendor", "invoice_number", "invoice_date", "total"]
        missing_keys = []
        for k in required_keys:
            f = fields.get(k)
            if not f or f.field_value is None or str(f.field_value).strip() == "":
                missing_keys.append(k)

        if missing_keys:
            msg = f"Missing mandatory field(s): {', '.join(missing_keys)}"
            rules.append(ValidationRuleResult(rule_name="required_fields_present", passed=False, message=msg, severity="error"))
            reasons.append(msg)
        else:
            rules.append(ValidationRuleResult(rule_name="required_fields_present", passed=True, message="All required fields present", severity="info"))

        # 2. Math Reconciliation: Subtotal + Tax == Total
        subtotal_f = fields.get("subtotal")
        tax_f = fields.get("tax")
        total_f = fields.get("total")

        subtotal = subtotal_f.field_value if subtotal_f and subtotal_f.field_value is not None else 0.0
        tax = tax_f.field_value if tax_f and tax_f.field_value is not None else 0.0
        total = total_f.field_value if total_f and total_f.field_value is not None else None

        if total is not None:
            expected_total = round(subtotal + tax, 2)
            diff = abs(expected_total - total)
            if diff <= tolerance:
                rules.append(ValidationRuleResult(
                    rule_name="math_subtotal_tax_total",
                    passed=True,
                    message=f"Total matches: subtotal ({subtotal}) + tax ({tax}) = {total}",
                    severity="info",
                ))
            else:
                msg = f"Math mismatch: subtotal ({subtotal}) + tax ({tax}) = {expected_total}, but total is {total} (diff: {diff:.2f})"
                rules.append(ValidationRuleResult(
                    rule_name="math_subtotal_tax_total",
                    passed=False,
                    message=msg,
                    severity="error",
                ))
                reasons.append(msg)

        # 3. Line Items Sum Check
        if line_items and subtotal > 0:
            items_sum = round(sum(item.amount for item in line_items), 2)
            diff_items = abs(items_sum - subtotal)
            if diff_items <= 0.15:
                rules.append(ValidationRuleResult(
                    rule_name="line_items_sum",
                    passed=True,
                    message=f"Line items sum ({items_sum}) reconciles with subtotal ({subtotal})",
                    severity="info",
                ))
            else:
                msg = f"Line items sum ({items_sum}) does not match subtotal ({subtotal})"
                rules.append(ValidationRuleResult(
                    rule_name="line_items_sum",
                    passed=False,
                    message=msg,
                    severity="warning",
                ))
                reasons.append(msg)

        # 4. Date Sanity Check
        inv_date_f = fields.get("invoice_date")
        due_date_f = fields.get("due_date")
        if inv_date_f and inv_date_f.field_value:
            try:
                inv_dt = datetime.strptime(str(inv_date_f.field_value), "%Y-%m-%d").date()
                today = date.today()
                # Document date should not be excessively in the future (> 30 days)
                if (inv_dt - today).days > 30:
                    msg = f"Invoice date {inv_dt} is unrealistically in the future"
                    rules.append(ValidationRuleResult(rule_name="date_sanity", passed=False, message=msg, severity="error"))
                    reasons.append(msg)
                elif due_date_f and due_date_f.field_value:
                    due_dt = datetime.strptime(str(due_date_f.field_value), "%Y-%m-%d").date()
                    if due_dt < inv_dt:
                        msg = f"Due date ({due_dt}) occurs before invoice date ({inv_dt})"
                        rules.append(ValidationRuleResult(rule_name="date_sanity", passed=False, message=msg, severity="error"))
                        reasons.append(msg)
                    else:
                        rules.append(ValidationRuleResult(rule_name="date_sanity", passed=True, message=f"Dates valid: issue {inv_dt}, due {due_dt}", severity="info"))
                else:
                    rules.append(ValidationRuleResult(rule_name="date_sanity", passed=True, message=f"Invoice date valid: {inv_dt}", severity="info"))
            except ValueError:
                msg = f"Invalid date format: {inv_date_f.field_value}"
                rules.append(ValidationRuleResult(rule_name="date_sanity", passed=False, message=msg, severity="error"))
                reasons.append(msg)

        # 5. Duplicate Check
        vendor_name = str(fields.get("vendor").field_value if fields.get("vendor") else "").strip()
        inv_num = str(fields.get("invoice_number").field_value if fields.get("invoice_number") else "").strip()
        if vendor_name and inv_num and total is not None:
            key = (vendor_name.lower(), inv_num.lower(), float(total))
            if key in self.existing_invoices:
                msg = f"Duplicate invoice detected: Vendor '{vendor_name}', Invoice #{inv_num}, Total {total}"
                rules.append(ValidationRuleResult(rule_name="duplicate_check", passed=False, message=msg, severity="error"))
                reasons.append(msg)
            else:
                rules.append(ValidationRuleResult(rule_name="duplicate_check", passed=True, message="No duplicate invoice found", severity="info"))

        # 6. Vendor Master Verification
        if vendor_name:
            # Check exact or case-insensitive match in vendor master
            matched_vendor = next((v for v in self.vendor_master if v.lower() == vendor_name.lower()), None)
            if matched_vendor:
                rules.append(ValidationRuleResult(
                    rule_name="vendor_master_check",
                    passed=True,
                    message=f"Vendor '{matched_vendor}' verified in master registry",
                    severity="info",
                ))
            else:
                msg = f"Vendor '{vendor_name}' not recognized in Master Vendor registry"
                rules.append(ValidationRuleResult(
                    rule_name="vendor_master_check",
                    passed=False,
                    message=msg,
                    severity="warning",
                ))
                reasons.append(msg)

        # 7. PO Matching
        po_f = fields.get("po_number")
        po_num = str(po_f.field_value).strip() if po_f and po_f.field_value else None
        if po_num:
            po_record = self.purchase_orders.get(po_num)
            if po_record:
                # Verify vendor and amount against PO
                po_vendor = po_record.get("vendor", "")
                po_total = po_record.get("total", 0.0)
                if po_vendor.lower() in vendor_name.lower() or vendor_name.lower() in po_vendor.lower():
                    if total is not None and abs(po_total - total) <= 0.10:
                        rules.append(ValidationRuleResult(
                            rule_name="po_matching",
                            passed=True,
                            message=f"PO {po_num} matched successfully (Vendor: {po_vendor}, Total: {po_total})",
                            severity="info",
                        ))
                    else:
                        msg = f"PO {po_num} amount mismatch: PO total {po_total} vs Invoice total {total}"
                        rules.append(ValidationRuleResult(rule_name="po_matching", passed=False, message=msg, severity="warning"))
                        reasons.append(msg)
                else:
                    msg = f"PO {po_num} vendor mismatch: PO issued to '{po_vendor}', invoice from '{vendor_name}'"
                    rules.append(ValidationRuleResult(rule_name="po_matching", passed=False, message=msg, severity="error"))
                    reasons.append(msg)
            else:
                rules.append(ValidationRuleResult(
                    rule_name="po_matching",
                    passed=True,
                    message=f"PO reference {po_num} noted (untracked)",
                    severity="info",
                ))

        # 8. Confidence Score & STP Evaluation
        confidences = [f.confidence for f in fields.values() if f.field_value is not None]
        mean_conf = round(sum(confidences) / max(len(confidences), 1), 4)

        has_blocking_errors = any(not r.passed and r.severity == "error" for r in rules)
        all_key_conf_above_threshold = all(
            fields[k].confidence >= conf_thresh for k in required_keys if k in fields and fields[k].field_value is not None
        )

        is_auto_approved = (not has_blocking_errors) and all_key_conf_above_threshold and (mean_conf >= conf_thresh)

        if not all_key_conf_above_threshold:
            low_conf_fields = [k for k in required_keys if k in fields and fields[k].confidence < conf_thresh]
            reasons.append(f"Confidence below threshold ({conf_thresh:.0%}) for: {', '.join(low_conf_fields)}")

        status = JobStatus.AUTO_APPROVED if is_auto_approved else JobStatus.NEEDS_REVIEW

        return ValidationSummary(
            is_approved=is_auto_approved,
            status=status,
            confidence_score=mean_conf,
            rules=rules,
            reasons=reasons,
        )
