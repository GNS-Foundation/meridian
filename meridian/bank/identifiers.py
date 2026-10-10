"""Synthetic identifiers (BANK-001-03/05, BANK-003-30).

IBAN per S11 as transcribed in BANK-001-05: Italian CIN over the 22-char BBAN body with the odd/even tables and
`mod 26`; ISO 7064 mod 97-10 check digits (BBAN + "IT00", A=10..Z=35, check = 98 - S mod 97). A-09: verified against
an educational source, not the ISO 13616 text. Synthetic ABI range 99000-99999 (A-08). MAV id: RAV-shaped
17 digits with PLACEHOLDER check digits (A-03), pluggable.
"""
from __future__ import annotations

import re
from collections.abc import Callable

_TAB = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_VAL_PARI = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
_VAL_DISPARI = [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]
SYNTHETIC_ABI_MIN, SYNTHETIC_ABI_MAX = 99000, 99999          # A-08
IBAN_IT_RE = re.compile(r"IT\d{2}[A-Z]\d{10}[A-Z0-9]{12}")
BIC_RE = re.compile(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?")


def cin_italiano(bban_body: str) -> str:
    """Italian CIN of the 22-char body ABI+CAB+conto (positions counted from 1: odd -> VAL_DISPARI)."""
    if len(bban_body) != 22:
        raise ValueError("BBAN body must be 22 chars (ABI 5 + CAB 5 + conto 12)")
    total = 0
    for i, ch in enumerate(bban_body.upper(), start=1):
        pos = _TAB.index(ch)
        total += _VAL_DISPARI[pos] if i % 2 == 1 else _VAL_PARI[pos]
    return chr(ord("A") + total % 26)


def mod97(s: str) -> int:
    n = 0
    for ch in s.upper():
        n = (n * 10 + int(ch)) % 97 if ch.isdigit() else (n * 100 + (ord(ch) - 55)) % 97
    return n


def iban_it(abi: str, cab: str, conto: str) -> str:
    body = f"{abi}{cab}{conto}"
    bban = cin_italiano(body) + body
    check = 98 - mod97(bban + "IT00")
    return f"IT{check:02d}{bban}"


def iban_is_valid(iban: str) -> bool:
    return len(iban) == 27 and iban.startswith("IT") and mod97(iban[4:] + iban[:4]) == 1 and cin_italiano(iban[5:]) == iban[4]


def synthetic_bic(institution: str, location: str = "MM", branch: str | None = "XXX") -> str:
    """ISO 9362 layout (S13): 4-letter institution code + IT + 2-char location + optional 3-char branch (A-08)."""
    bic = f"{institution.upper()}IT{location.upper()}" + (branch.upper() if branch else "")
    if not BIC_RE.fullmatch(bic):
        raise ValueError(f"not a BIC shape: {bic}")
    return bic


# ---- MAV identifier (A-03): N1 (5, 80000-99999) + N2 (9) + CIN10 (1) + CIN93 (2) = 17 digits ----
def _placeholder_cin10(digits: str) -> str:
    return str(sum(map(int, digits)) % 10)


def _placeholder_cin93(digits: str) -> str:
    return f"{sum(map(int, digits)) % 93:02d}"


def mav_id(n1: str, n2: str, cin10: Callable[[str], str] = _placeholder_cin10, cin93: Callable[[str], str] = _placeholder_cin93) -> str:
    """RAV-shaped MAV identifier with PLACEHOLDER check digits (A-03). The algorithms are pluggable."""
    if not (len(n1) == 5 and n1.isdigit() and 80000 <= int(n1) <= 99999):
        raise ValueError("N1 must be 5 digits in 80000-99999")
    if not (len(n2) == 9 and n2.isdigit()):
        raise ValueError("N2 must be 9 digits")
    d = n1 + n2
    return d + cin10(d) + cin93(d)


def fiscal_code_like(seed_text: str) -> str:
    """Synthetic 16-char code that is NOT a valid codice fiscale by construction (D-11): positions 1-6 of a real
    code are letters; this one puts digits there, so no checksum can make it real. Deterministic from the text."""
    import hashlib
    h = hashlib.blake2b(seed_text.encode(), digest_size=8).hexdigest().upper()
    digits = "".join(ch for ch in h if ch.isdigit()) or "0000000"
    digits = (digits * 3)[:6]
    letters = "".join(ch for ch in h if ch.isalpha()) or "ZZZZZZZZZZ"
    letters = (letters * 3)[:10]
    return (digits + letters)[:16]
