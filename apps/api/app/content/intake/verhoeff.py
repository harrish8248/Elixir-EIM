"""Verhoeff Checksum Algorithm Implementation.

Used for Indian Aadhaar 12-digit number validation and checksum verification.
"""

# Multiplication table d (dihedral group D5 / D8)
D_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table p
P_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse table inv
INV_TABLE = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def validate_aadhaar(aadhaar: str | int | None) -> bool:
    """Validate 12-digit Indian Aadhaar number using the Verhoeff checksum algorithm.

    Rejects numbers not starting with 2-9 (0 and 1 are invalid initial digits in UIDAI specs).
    """
    if aadhaar is None:
        return False
    clean = "".join(c for c in str(aadhaar) if c.isdigit())
    if len(clean) != 12:
        return False
    # UIDAI specs: First digit cannot be 0 or 1
    if clean[0] in ("0", "1"):
        return False

    c = 0
    for i, item in enumerate(reversed([int(d) for d in clean])):
        c = D_TABLE[c][P_TABLE[i % 8][item]]
    return c == 0


def generate_verhoeff_check_digit(num_str: str) -> str:
    """Generate Verhoeff check digit for an 11-digit prefix."""
    digits = [int(c) for c in num_str if c.isdigit()]
    c = 0
    for i, item in enumerate(reversed(digits)):
        c = D_TABLE[c][P_TABLE[(i + 1) % 8][item]]
    return str(INV_TABLE[c])

