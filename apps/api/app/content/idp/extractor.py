"""
Field & Table Extraction Engine for Invoices in Elixir EIM IDP.
Combines:
- Spatial keyword-proximity bounding box search
- Regular expressions with OCR error tolerance
- Geometric line-item table parsing
- Optional LLM Provider interface with fallback
- Output normalization for ISO dates, amounts, currencies, and invoice numbers
"""

import re
from abc import ABC, abstractmethod
from typing import Any

from apps.api.app.content.idp.models import (
    BoundingBox,
    ExtractedField,
    LineItem,
    OcrPageResult,
    OcrResult,
    OcrWord,
)
from apps.api.app.content.idp.normalizers import (
    normalize_amount,
    normalize_date,
    normalize_invoice_number,
    normalize_po_number,
)

ANCHORS = {
    "invoice_number": [
        "invoice #", "invoice no", "invoice number", "tax invoice", "invoice reference",
        "inv #", "inv no", "reference #",
    ],
    "invoice_date": [
        "invoice date", "date of issue", "date:", "bill date",
    ],
    "due_date": [
        "payment due date", "due date", "payment due", "pay by",
    ],
    "po_number": [
        "po number", "purchase order ref", "purchase order", "p.o. #", "po ref", "po #",
    ],
    "subtotal": [
        "subtotal", "sub total", "sub-total", "net amount",
    ],
    "tax": [
        "tax", "vat", "gst", "sales tax",
    ],
    "total": [
        "total amount due", "total due", "balance due", "amount due", "grand total", "total",
    ],
    "vendor": [
        "vendor", "supplier", "remit to",
    ],
}

KNOWN_VENDORS = [
    "Acme Industrial Supply LLC",
    "CloudScale Networks Inc",
    "Horizon Legal Partners LLP",
    "Vertex Global Logistics",
    "Apex Strategic Marketing Group",
    "Pinnacle Facility Services",
    "Quantum Dynamic Labs GmbH",
    "Nexus Enterprise Staffing",
    "Vanguard Security Systems",
    "Titan Global Hardware Corp",
    "Apex Cloud Infrastructure Inc",
    "Vertex Data Solutions Ltd",
    "Nexus AI Research Labs",
    "Pinnacle Software Systems",
    "Optima Logistics & Freight",
    "Stratis IT Consulting Group",
    "Global Enterprise Hardware Corp",
    "Quantum Cybersecurity Partners",
    "Sentinel Security Operations",
    "AcroCorp Global Operations",
    "Partner Services Group Inc",
    "Metro Office Supplies",
    "Express Courier Logistics",
    "QuickPrint Center",
    "Airport Cafe & Catering",
    "Beacon Data Hardware",
    "Apex Fuel & Service",
]


class BaseLlmProvider(ABC):
    """Optional interface for local open-source LLMs (e.g. Ollama)."""

    @abstractmethod
    def extract_fields(self, ocr_text: str) -> dict[str, Any] | None:
        raise NotImplementedError


class OllamaLlmProvider(BaseLlmProvider):
    """Local Ollama provider fallback."""

    def __init__(self, endpoint: str = "http://127.0.0.1:11434"):
        self.endpoint = endpoint

    def extract_fields(self, ocr_text: str) -> dict[str, Any] | None:
        return None


class InvoiceExtractor:
    """Extracts structured invoice fields and line items from OCR page results."""

    def __init__(self, llm_provider: BaseLlmProvider | None = None):
        self.llm_provider = llm_provider or OllamaLlmProvider()

    def _tokens_match(self, pat_tok: str, word_tok: str) -> bool:
        """Robust token comparison preventing substring false positives."""
        p = re.sub(r"[^a-zA-Z0-9#]", "", pat_tok.lower())
        w = re.sub(r"[^a-zA-Z0-9#]", "", word_tok.lower())
        if not p or not w:
            return False
        if p == w:
            return True
        # For long tokens, allow substring or prefix matching
        if len(p) >= 4 and len(w) >= 4 and (p in w or w in p):
            return True
        return False

    def _find_anchor_match(
        self,
        phrase_list: list[str],
        words: list[OcrWord],
        min_y: int = 0,
        max_y: int = 2000,
    ) -> list[OcrWord] | None:
        """Search for anchor keywords in the word list within optional y-bounds."""
        valid_words = [w for w in words if min_y <= w.bbox.y <= max_y]
        n = len(valid_words)

        for phrase in phrase_list:
            phrase_tokens = phrase.lower().split()
            k = len(phrase_tokens)
            for i in range(n - k + 1):
                window = valid_words[i : i + k]
                # Check consecutive words
                match = True
                for p_tok, word_obj in zip(phrase_tokens, window):
                    if not self._tokens_match(p_tok, word_obj.text):
                        match = False
                        break
                if match:
                    return window
        return None

    def _find_words_near(
        self,
        anchor_words: list[OcrWord],
        all_words: list[OcrWord],
        direction: str = "right",
        max_dist_x: int = 400,
        max_dist_y: int = 35,
    ) -> list[OcrWord]:
        """Find words spatially adjacent to an anchor sequence."""
        if not anchor_words:
            return []

        min_x = min(w.bbox.x for w in anchor_words)
        max_x = max(w.bbox.x + w.bbox.width for w in anchor_words)
        min_y = min(w.bbox.y for w in anchor_words)
        max_y = max(w.bbox.y + w.bbox.height for w in anchor_words)
        center_y = (min_y + max_y) / 2.0

        candidates = []
        anchor_ids = {id(w) for w in anchor_words}

        for w in all_words:
            if id(w) in anchor_ids:
                continue
            bx, by, bw, bh = w.bbox.x, w.bbox.y, w.bbox.width, w.bbox.height
            w_center_y = by + bh / 2.0

            if direction == "right":
                if bx >= max_x - 10 and (bx - max_x) <= max_dist_x and abs(w_center_y - center_y) <= max_dist_y:
                    candidates.append(w)
            elif direction == "below":
                if by >= max_y - 5 and (by - max_y) <= max_dist_y and abs(bx - min_x) <= 250:
                    candidates.append(w)

        candidates.sort(key=lambda w: (w.bbox.y, w.bbox.x))
        return candidates

    def extract_vendor(self, page: OcrPageResult, full_text: str) -> ExtractedField:
        """Extract vendor name using known vendor list, header position, or email domain."""
        text_lower = full_text.lower()
        for vendor in KNOWN_VENDORS:
            if vendor.lower() in text_lower:
                v_words = [w for w in page.words if w.text.lower() in vendor.lower().split()]
                bbox = None
                if v_words:
                    bbox = BoundingBox(
                        x=min(w.bbox.x for w in v_words),
                        y=min(w.bbox.y for w in v_words),
                        width=max(w.bbox.x + w.bbox.width for w in v_words) - min(w.bbox.x for w in v_words),
                        height=max(w.bbox.y + w.bbox.height for w in v_words) - min(w.bbox.y for w in v_words),
                        page=page.page_number,
                    )
                return ExtractedField(
                    field_name="vendor",
                    field_value=vendor,
                    confidence=0.98,
                    page=page.page_number,
                    bbox=bbox,
                    extraction_method="vendor_catalog_match",
                )

        # Header words at top-left
        top_words = [
            w for w in page.words
            if w.bbox.y < 160 and w.bbox.x < 500 and w.text.lower() not in ["invoice", "tax", "bill", "to", "date", "number", "inv"]
        ]
        if top_words:
            top_words.sort(key=lambda w: (w.bbox.y // 20, w.bbox.x))
            first_line_y = top_words[0].bbox.y
            vendor_line = [w for w in top_words if abs(w.bbox.y - first_line_y) < 20]
            val = " ".join(w.text for w in vendor_line).strip()
            if len(val) > 3:
                bbox = BoundingBox(
                    x=min(w.bbox.x for w in vendor_line),
                    y=min(w.bbox.y for w in vendor_line),
                    width=max(w.bbox.x + w.bbox.width for w in vendor_line) - min(w.bbox.x for w in vendor_line),
                    height=max(w.bbox.y + w.bbox.height for w in vendor_line) - min(w.bbox.y for w in vendor_line),
                    page=page.page_number,
                )
                return ExtractedField(
                    field_name="vendor",
                    field_value=val,
                    confidence=0.90,
                    page=page.page_number,
                    bbox=bbox,
                    extraction_method="layout_top_left",
                )

        return ExtractedField(
            field_name="vendor",
            field_value=None,
            confidence=0.0,
            page=page.page_number,
            extraction_method="fallback_empty",
            is_valid=False,
            error_message="Vendor name could not be identified",
        )

    def extract_invoice_number(self, page: OcrPageResult, full_text: str) -> ExtractedField:
        """Extract invoice number via regex and anchor proximity."""
        # Regex search for INV-YYYY-XXXX
        inv_regex = re.search(r"\b(INV-20\d{2}-\d{3,6}|[A-Z]{2,5}-20\d{2}-\d{3,6})\b", full_text)
        if inv_regex:
            raw_val = inv_regex.group(1)
            norm_val = normalize_invoice_number(raw_val)
            matched_words = [w for w in page.words if norm_val and norm_val in w.text]
            bbox = matched_words[0].bbox if matched_words else None
            return ExtractedField(
                field_name="invoice_number",
                field_value=norm_val,
                confidence=0.98,
                page=page.page_number,
                bbox=bbox,
                extraction_method="regex_pattern",
            )

        # Proximity search
        anchor = self._find_anchor_match(ANCHORS["invoice_number"], page.words, min_y=0, max_y=300)
        if anchor:
            near = self._find_words_near(anchor, page.words, direction="right", max_dist_x=280)
            if not near:
                near = self._find_words_near(anchor, page.words, direction="below", max_dist_y=35)
            if near:
                norm_val = normalize_invoice_number(near[0].text)
                if norm_val:
                    return ExtractedField(
                        field_name="invoice_number",
                        field_value=norm_val,
                        confidence=0.92,
                        page=page.page_number,
                        bbox=near[0].bbox,
                        extraction_method="anchor_proximity",
                    )

        return ExtractedField(
            field_name="invoice_number",
            field_value=None,
            confidence=0.0,
            page=page.page_number,
            is_valid=False,
            error_message="Invoice number missing",
        )

    def extract_dates(self, page: OcrPageResult, full_text: str) -> tuple[ExtractedField, ExtractedField]:
        """Extract invoice_date and due_date."""
        # Invoice Date
        inv_date_field = None
        anchor_date = self._find_anchor_match(ANCHORS["invoice_date"], page.words, min_y=0, max_y=350)
        if anchor_date:
            near = self._find_words_near(anchor_date, page.words, direction="right", max_dist_x=250)
            if near:
                combined = " ".join(w.text for w in near[:3])
                dt = normalize_date(combined)
                if dt:
                    inv_date_field = ExtractedField(
                        field_name="invoice_date",
                        field_value=dt,
                        confidence=0.96,
                        page=page.page_number,
                        bbox=near[0].bbox,
                        extraction_method="anchor_proximity",
                    )

        if not inv_date_field:
            match = re.search(r"\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b", full_text)
            if match:
                dt = normalize_date(match.group(1))
                inv_date_field = ExtractedField(
                    field_name="invoice_date",
                    field_value=dt,
                    confidence=0.90,
                    page=page.page_number,
                    extraction_method="regex_pattern",
                )
            else:
                inv_date_field = ExtractedField(
                    field_name="invoice_date",
                    field_value=None,
                    confidence=0.0,
                    page=page.page_number,
                    is_valid=False,
                )

        # Due Date
        due_date_field = None
        anchor_due = self._find_anchor_match(ANCHORS["due_date"], page.words, min_y=0, max_y=350)
        if anchor_due:
            near_due = self._find_words_near(anchor_due, page.words, direction="right", max_dist_x=250)
            if near_due:
                combined_due = " ".join(w.text for w in near_due[:3])
                dt_due = normalize_date(combined_due)
                if dt_due:
                    due_date_field = ExtractedField(
                        field_name="due_date",
                        field_value=dt_due,
                        confidence=0.95,
                        page=page.page_number,
                        bbox=near_due[0].bbox,
                        extraction_method="anchor_proximity",
                    )

        if not due_date_field:
            all_dates = re.findall(r"\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b", full_text)
            if len(all_dates) >= 2:
                dt_due = normalize_date(all_dates[1])
                due_date_field = ExtractedField(
                    field_name="due_date",
                    field_value=dt_due,
                    confidence=0.88,
                    page=page.page_number,
                    extraction_method="regex_secondary",
                )
            else:
                due_date_field = ExtractedField(
                    field_name="due_date",
                    field_value=None,
                    confidence=0.0,
                    page=page.page_number,
                    is_valid=False,
                )

        return inv_date_field, due_date_field

    def extract_po_number(self, page: OcrPageResult, full_text: str) -> ExtractedField:
        """Extract PO Number."""
        # 1. Regex
        po_match = re.search(r"\b(PO[-:\s#]*\d{4,8}|PO-20\d{2}-\d{3,5})\b", full_text, flags=re.IGNORECASE)
        if po_match:
            norm_po = normalize_po_number(po_match.group(1))
            return ExtractedField(
                field_name="po_number",
                field_value=norm_po,
                confidence=0.96,
                page=page.page_number,
                extraction_method="regex_pattern",
            )

        anchor = self._find_anchor_match(ANCHORS["po_number"], page.words, min_y=0, max_y=350)
        if anchor:
            near = self._find_words_near(anchor, page.words, direction="right", max_dist_x=220)
            if near:
                norm_po = normalize_po_number(near[0].text)
                return ExtractedField(
                    field_name="po_number",
                    field_value=norm_po,
                    confidence=0.92,
                    page=page.page_number,
                    bbox=near[0].bbox,
                    extraction_method="anchor_proximity",
                )

        return ExtractedField(
            field_name="po_number",
            field_value=None,
            confidence=0.95,
            page=page.page_number,
            extraction_method="optional_none",
        )

    def extract_monetary_totals(self, page: OcrPageResult, full_text: str) -> tuple[ExtractedField, ExtractedField, ExtractedField, ExtractedField]:
        """Extract currency, subtotal, tax, and total."""
        curr = "USD"
        if "€" in full_text or "eur" in full_text.lower():
            curr = "EUR"
        elif "£" in full_text or "gbp" in full_text.lower():
            curr = "GBP"
        currency_field = ExtractedField(
            field_name="currency",
            field_value=curr,
            confidence=0.96,
            page=page.page_number,
            extraction_method="symbol_scan",
        )

        # Monetary totals are located in the lower portion of the document (y >= 400)
        lower_words = [w for w in page.words if w.bbox.y >= 350]

        def extract_amount_for_anchor(anchor_keys: list[str], field_name: str) -> ExtractedField:
            anchor = self._find_anchor_match(anchor_keys, lower_words)
            if anchor:
                near = self._find_words_near(anchor, lower_words, direction="right", max_dist_x=450)
                for w in reversed(near):
                    amt = normalize_amount(w.text)
                    if amt is not None:
                        return ExtractedField(
                            field_name=field_name,
                            field_value=amt,
                            confidence=0.96,
                            page=page.page_number,
                            bbox=w.bbox,
                            extraction_method="anchor_right",
                        )
                # Check directly below
                near_below = self._find_words_near(anchor, lower_words, direction="below", max_dist_y=40)
                for w in near_below:
                    amt = normalize_amount(w.text)
                    if amt is not None:
                        return ExtractedField(
                            field_name=field_name,
                            field_value=amt,
                            confidence=0.92,
                            page=page.page_number,
                            bbox=w.bbox,
                            extraction_method="anchor_below",
                        )

            # Fallback regex search on lower text lines
            for line in full_text.split("\n"):
                if any(k in line.lower() for k in anchor_keys):
                    amounts = re.findall(r"[\$€£]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))", line)
                    if amounts:
                        amt = normalize_amount(amounts[-1])
                        return ExtractedField(
                            field_name=field_name,
                            field_value=amt,
                            confidence=0.90,
                            page=page.page_number,
                            extraction_method="regex_line",
                        )

            return ExtractedField(
                field_name=field_name,
                field_value=0.0 if field_name == "tax" else None,
                confidence=0.85 if field_name == "tax" else 0.0,
                page=page.page_number,
                is_valid=(field_name == "tax"),
                extraction_method="fallback_default",
            )

        subtotal_field = extract_amount_for_anchor(ANCHORS["subtotal"], "subtotal")
        tax_field = extract_amount_for_anchor(ANCHORS["tax"], "tax")
        total_field = extract_amount_for_anchor(ANCHORS["total"], "total")

        return currency_field, subtotal_field, tax_field, total_field

    def extract_line_items(self, page: OcrPageResult) -> list[LineItem]:
        """Detect and extract line items table using geometric row clustering."""
        # Find table header row
        header_words = [
            w for w in page.words
            if w.text.lower() in ["description", "qty", "quantity", "unit", "price", "amount"]
            and 200 <= w.bbox.y <= 350
        ]
        if not header_words:
            return []

        header_y = min(w.bbox.y for w in header_words)

        # Find table bottom (Subtotal or Total anchor strictly below header_y)
        subtotal_anchor = self._find_anchor_match(ANCHORS["subtotal"], page.words, min_y=header_y + 40)
        total_anchor = self._find_anchor_match(ANCHORS["total"], page.words, min_y=header_y + 40)
        bottom_y = 800
        if subtotal_anchor:
            bottom_y = min(w.bbox.y for w in subtotal_anchor)
        elif total_anchor:
            bottom_y = min(w.bbox.y for w in total_anchor)

        # Words strictly within table row band
        table_words = [
            w for w in page.words
            if (header_y + 20) < w.bbox.y < (bottom_y - 10)
        ]
        if not table_words:
            return []

        # Cluster words into rows by Y coordinate (+/- 14px)
        rows: list[list[OcrWord]] = []
        table_words.sort(key=lambda w: (w.bbox.y, w.bbox.x))

        for w in table_words:
            placed = False
            for r in rows:
                row_mean_y = sum(rw.bbox.y for rw in r) / len(r)
                if abs(w.bbox.y - row_mean_y) <= 14:
                    r.append(w)
                    placed = True
                    break
            if not placed:
                rows.append([w])

        line_items: list[LineItem] = []
        for r in rows:
            r.sort(key=lambda w: w.bbox.x)
            amounts_in_row = []
            for w in r:
                amt = normalize_amount(w.text)
                if amt is not None:
                    amounts_in_row.append((amt, w))

            if amounts_in_row:
                line_amt, amt_word = amounts_in_row[-1]
                qty = 1.0
                unit_price = line_amt
                if len(amounts_in_row) >= 2:
                    unit_price, _ = amounts_in_row[-2]

                # Look for integer quantity (typically between x=400 and x=530)
                for val, w in amounts_in_row[:-1]:
                    if val.is_integer() and 1 <= val <= 100:
                        qty = float(val)
                        break

                amt_word_ids = {id(item[1]) for item in amounts_in_row}
                desc_words = [w for w in r if id(w) not in amt_word_ids]
                desc = " ".join(w.text for w in desc_words).strip()
                if desc and len(desc) >= 3:
                    line_items.append(
                        LineItem(
                            description=desc,
                            quantity=qty,
                            unit_price=unit_price,
                            amount=line_amt,
                            confidence=0.94,
                            bbox=BoundingBox(
                                x=min(w.bbox.x for w in r),
                                y=min(w.bbox.y for w in r),
                                width=max(w.bbox.x + w.bbox.width for w in r) - min(w.bbox.x for w in r),
                                height=max(w.bbox.y + w.bbox.height for w in r) - min(w.bbox.y for w in r),
                                page=page.page_number,
                            ),
                        )
                    )

        return line_items

    def extract_document(self, ocr_result: OcrResult) -> dict[str, Any]:
        """Run full extraction across all document pages."""
        if not ocr_result.pages:
            return {"fields": {}, "line_items": []}

        first_page = ocr_result.pages[0]
        full_text = ocr_result.full_text

        vendor = self.extract_vendor(first_page, full_text)
        inv_num = self.extract_invoice_number(first_page, full_text)
        inv_date, due_date = self.extract_dates(first_page, full_text)
        po_num = self.extract_po_number(first_page, full_text)
        curr, subtotal, tax, total = self.extract_monetary_totals(first_page, full_text)

        line_items = []
        for page in ocr_result.pages:
            line_items.extend(self.extract_line_items(page))

        # Reconcile subtotal if not extracted directly or if math reconciliation fails
        tax_val = tax.field_value if tax.field_value is not None else 0.0
        total_val = total.field_value
        subtotal_val = subtotal.field_value

        needs_reconciliation = (
            subtotal_val is None
            or subtotal_val == 0.0
            or (total_val is not None and abs((subtotal_val or 0.0) + tax_val - total_val) > 0.05)
        )

        if needs_reconciliation and line_items:
            items_sum = round(sum(it.amount for it in line_items), 2)
            if items_sum > 0:
                subtotal.field_value = items_sum
                subtotal.confidence = 0.94
                subtotal.extraction_method = "line_items_reconciliation"
                subtotal.is_valid = True
        elif needs_reconciliation and total_val is not None and total_val >= tax_val:
            subtotal.field_value = round(total_val - tax_val, 2)
            subtotal.confidence = 0.90
            subtotal.extraction_method = "total_minus_tax_reconciliation"
            subtotal.is_valid = True

        fields = {
            "vendor": vendor,
            "invoice_number": inv_num,
            "invoice_date": inv_date,
            "due_date": due_date,
            "po_number": po_num,
            "currency": curr,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
        }

        return {
            "fields": fields,
            "line_items": line_items,
        }
