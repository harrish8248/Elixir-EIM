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
    "₹": "INR",
    "RS.": "INR",
    "RS": "INR",
    "INR": "INR",
    "RUPEES": "INR",
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


def normalize_date(value: Any, prefer_dmy: bool = False) -> str | None:
    """Normalize any date representation to ISO 8601 (YYYY-MM-DD)."""
    if not value:
        return None
    val_str = str(value).strip()

    # 1. Direct ISO 8601: YYYY-MM-DD
    iso_match = re.search(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b", val_str)
    if iso_match:
        y, m, d = iso_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # 2. DD-Mon-YYYY or DD/Mon/YYYY (e.g. 01-Apr-2026, 24/Oct/2026)
    mon_match = re.search(
        r"\b(0?[1-9]|[12]\d|3[01])[-/.](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/.](20\d{2})\b",
        val_str,
        re.IGNORECASE,
    )
    if mon_match:
        d, mon_str, y = mon_match.groups()
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        m = month_map.get(mon_str.lower()[:3], 1)
        return f"{int(y):04d}-{m:02d}-{int(d):02d}"

    # 3. Handle numeric slash/hyphen dates
    num_match = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", val_str)
    if num_match:
        p1, p2, y_int = int(num_match.group(1)), int(num_match.group(2)), int(num_match.group(3))
        if p1 > 12:  # Must be Day/Month/Year
            d_val, m_val = p1, p2
        elif p2 > 12:  # Must be Month/Day/Year
            m_val, d_val = p1, p2
        elif prefer_dmy:  # Ambiguous, but prefer DMY (Indian/UK)
            d_val, m_val = p1, p2
        else:  # Ambiguous, default to MDY (US)
            m_val, d_val = p1, p2
        if 1 <= m_val <= 12 and 1 <= d_val <= 31:
            return f"{y_int:04d}-{m_val:02d}-{d_val:02d}"

    # 4. Textual month parsing
    for fmt in [
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d/%b/%Y",
        "%d/%B/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y-%m-%d",
        "%d/%m/%Y" if prefer_dmy else "%m/%d/%Y",
        "%m/%d/%Y" if prefer_dmy else "%d/%m/%Y",
    ]:
        try:
            clean = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", val_str)
            dt = datetime.strptime(clean, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_amount(value: Any) -> float | None:
    """Normalize numeric amount to 2-decimal float, handling Indian number grouping and currency symbols."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)

    val_str = str(value).strip()
    if not val_str:
        return None

    # Handle negative amounts
    is_negative = False
    if val_str.startswith("(") and val_str.endswith(")"):
        is_negative = True
        val_str = val_str[1:-1]
    elif val_str.startswith("-"):
        is_negative = True
        val_str = val_str[1:]

    # Remove currency words/symbols and trailing '/-' notation
    val_str = re.sub(r"(?:INR|₹|Rs\.?|RS\.?|USD|\$|EUR|€|GBP|£)", "", val_str, flags=re.IGNORECASE)
    val_str = val_str.rstrip("/- \t\n")

    cleaned = re.sub(r"[^\d,.]", "", val_str).rstrip(".")
    if not cleaned:
        return None

    # Determine European (1.234,56) vs US/Indian (1,23,456.56 or 1,234.56)
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
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
