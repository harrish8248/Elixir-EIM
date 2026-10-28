"""
Normalizers for extracted fields in Elixir EIM IDP.
Ensures standardized formats:
- Dates to ISO 8601 (YYYY-MM-DD)
- Amounts to 2-decimal floats
- Currency symbols to ISO 4217 3-letter codes
- Invoice / PO numbers to clean alphanumeric strings
"""

import re
from datetime import datetime
from typing import Any

CURRENCY_MAP = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "¥": "JPY",
    "JPY": "JPY",
    "C$": "CAD",
    "CAD": "CAD",
    "A$": "AUD",
    "AUD": "AUD",
    "CHF": "CHF",
}

DATE_PATTERNS = [
    # 2026-05-08 or 2026/05/08
    r"(\b20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b)",
    # 05/08/2026 or 05-08-2026
    r"(\b\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}\b)",
    # May 8, 2026 or May 08 2026 or 8 May 2026
    r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,-]+\d{1,2}(?:st|nd|rd|th)?[\s.,-]+20\d{2}\b)",
    r"(\b\d{1,2}(?:st|nd|rd|th)?[\s.,-]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,-]+20\d{2}\b)",
]


def normalize_date(value: Any) -> str | None:
    """Normalize any date representation to ISO 8601 (YYYY-MM-DD)."""
    if not value:
        return None
    val_str = str(value).strip()

    # Direct ISO 8601 check: YYYY-MM-DD
    iso_match = re.search(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b", val_str)
    if iso_match:
        y, m, d = iso_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Month day year: e.g. 10/25/2026 or 10-25-2026
    mdy_match = re.search(r"\b(0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])[-/.](20\d{2})\b", val_str)
    if mdy_match:
        m, d, y = mdy_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Day month year: e.g. 25/10/2026
    dmy_match = re.search(r"\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.](20\d{2})\b", val_str)
    if dmy_match:
        d, m, y = dmy_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Textual month parsing: "May 8, 2026" or "8 May 2026"
    for fmt in [
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]:
        try:
            # clean ordinal suffixes like 1st, 2nd, 3rd, 4th
            clean = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", val_str)
            dt = datetime.strptime(clean, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_amount(value: Any) -> float | None:
    """Normalize numeric amount to 2-decimal float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)

    val_str = str(value).strip()
    if not val_str:
        return None

    # Handle negative amounts formatted as (123.45) or -123.45
    is_negative = False
    if val_str.startswith("(") and val_str.endswith(")"):
        is_negative = True
        val_str = val_str[1:-1]
    elif val_str.startswith("-"):
        is_negative = True
        val_str = val_str[1:]

    # Remove currency symbols and non-numeric noise except commas and dots
    cleaned = re.sub(r"[^\d,.]", "", val_str)
    if not cleaned:
        return None

    # Determine European (1.234,56) vs US (1,234.56) format
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # European format: replace . with empty, , with .
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # US format: remove comma
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        # Check if single comma is decimal separator (e.g. 1234,50)
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            cleaned = f"{parts[0]}.{parts[1]}"
        else:
            cleaned = cleaned.replace(",", "")

    try:
        amt = float(cleaned)
        if is_negative:
            amt = -amt
        return round(amt, 2)
    except ValueError:
        return None


def normalize_currency(value: Any) -> str:
    """Normalize currency symbol or code to standard ISO 4217 code."""
    if not value:
        return "USD"
    val_str = str(value).strip().upper()
    for sym, code in CURRENCY_MAP.items():
        if sym in val_str or code == val_str:
            return code
    return "USD"


def normalize_invoice_number(value: Any) -> str | None:
    """Clean and standardize an invoice number."""
    if not value:
        return None
    val_str = str(value).strip()
    # Remove leading labels like "Invoice #:", "Invoice No.", "Invoice Reference:" but preserve "INV-" prefix
    val_str = re.sub(r"^(?:Invoice\s*(?:#|No\.?|Number|Ref)?:?|Tax\s*Invoice:?|Bill\s*#?:?)\s*", "", val_str, flags=re.IGNORECASE).strip()
    # Remove trailing punctuation like dots or colons
    val_str = val_str.strip(".:;,#")
    # Clean inner whitespaces
    val_str = re.sub(r"\s+", "", val_str)
    return val_str if val_str else None


def normalize_po_number(value: Any) -> str | None:
    """Clean and standardize a PO number."""
    if not value:
        return None
    val_str = str(value).strip()
    # Remove leading common labels but preserve "PO-" prefix if present
    val_str = re.sub(r"^(?:Purchase\s*Order\s*(?:#|No\.?|Number|Ref)?:?|P\.?O\.?\s*(?:#|No\.?|Number|Ref):\s*)\s*", "", val_str, flags=re.IGNORECASE).strip()
    val_str = val_str.strip(".:;,#")
    val_str = re.sub(r"\s+", "", val_str)
    # Ensure PO- prefix is uniform if begins with digits or minus
    if val_str.startswith("-"):
        val_str = f"PO{val_str}"
    return val_str if val_str else None
