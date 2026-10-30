"""Luhn Mod-10 Checksum Algorithm Implementation.

Used for validating credit and debit payment card numbers (Visa, Mastercard, Amex, RuPay).
"""


def validate_luhn(card_number: str | None) -> bool:
    """Validate payment card number using the Luhn Mod-10 algorithm.

    Length must be between 13 and 19 digits.
    """
    if card_number is None:
        return False
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += d

    return checksum % 10 == 0

