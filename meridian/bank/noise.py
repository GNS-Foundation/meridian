"""Noise operators (BANK-003-05 remittance, BANK-003-08 counterparty names). Explicit, composable, recorded.

Semantics are those of corpus/bank/README.md §Operators (the corpus is the contract):
  truncate_to(n)                first n chars
  upper()                       uppercase
  strip_accents()               NFD, combining marks removed
  drop_separators()             hyphens removed
  transpose_adjacent_digits(k)  swap the k-th and (k+1)-th DIGIT of the string (digits only, 0-based)
  drop_token(i)                 remove the i-th whitespace-separated token (0-based)
  prepend_bank_boilerplate()    prefix "BONIFICO SEPA A VS FAVORE DA "
  concat_two_references()       keep the structured tokens (REF/DOC/CUST pairs) and insert a second REF (+1) after the first
  initials()                    "SURNAME G."
  swap_surname_given()          "Surname Given"
  truncate_to_yyy_width()       first 40 chars (record 63 YYY pos. 41-80)
  third_party_payer()           handled by the materialiser (different holder), recorded like any other op
"""
from __future__ import annotations

import re
import unicodedata

BOILERPLATE = "BONIFICO SEPA A VS FAVORE DA "
_OP_RE = re.compile(r"^([a-z_]+)\((.*)\)$")
STRUCTURED_KEYS = ("REF", "DOC", "CUST")


def parse_op(op: str) -> tuple[str, list[str]]:
    m = _OP_RE.match(op.strip())
    if not m:
        raise ValueError(f"malformed operator: {op!r}")
    args = [a.strip() for a in m.group(2).split(",") if a.strip()]
    return m.group(1), args


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def transpose_adjacent_digits(s: str, k: int) -> str:
    idx = [i for i, ch in enumerate(s) if ch.isdigit()]
    if k + 1 >= len(idx):
        return s
    a, b = idx[k], idx[k + 1]
    chars = list(s)
    chars[a], chars[b] = chars[b], chars[a]
    return "".join(chars)


def drop_token(s: str, i: int) -> str:
    toks = s.split(" ")
    return " ".join(t for j, t in enumerate(toks) if j != i)


def concat_two_references(s: str) -> str:
    toks = s.split()
    pairs: list[tuple[str, str]] = []
    j = 0
    while j + 1 < len(toks):
        if toks[j] in STRUCTURED_KEYS:
            pairs.append((toks[j], toks[j + 1])); j += 2
        else:
            j += 1
    out: list[str] = []
    inserted = False
    for key, val in pairs:
        out += [key, val]
        if key == "REF" and not inserted:
            m = re.search(r"(\d+)$", val)
            if m:
                n = m.group(1)
                out += ["REF", val[: -len(n)] + str(int(n) + 1).rjust(len(n), "0")]
            inserted = True
    return " ".join(out) if out else s


def apply_remittance(text: str, ops: list[str]) -> str:
    for op in ops:
        name, args = parse_op(op)
        if name == "truncate_to":
            text = text[: int(args[0])]
        elif name == "upper":
            text = text.upper()
        elif name == "strip_accents":
            text = strip_accents(text)
        elif name == "drop_separators":
            text = text.replace("-", "")
        elif name == "transpose_adjacent_digits":
            text = transpose_adjacent_digits(text, int(args[0]))
        elif name == "drop_token":
            text = drop_token(text, int(args[0]))
        elif name == "prepend_bank_boilerplate":
            text = BOILERPLATE + text
        elif name == "concat_two_references":
            text = concat_two_references(text)
        else:
            raise ValueError(f"unknown remittance operator: {op!r}")
    return text


def initials(name: str) -> str:
    parts = name.split()
    surname, given = parts[-1], parts[0]
    return f"{surname.upper()} {given[0].upper()}."


def swap_surname_given(name: str) -> str:
    parts = name.split()
    return " ".join([parts[-1]] + parts[:-1])


def apply_name(name: str, ops: list[str]) -> str:
    for op in ops:
        kind, _ = parse_op(op)
        if kind == "initials":
            name = initials(name)
        elif kind == "swap_surname_given":
            name = swap_surname_given(name)
        elif kind == "truncate_to_yyy_width":
            name = name[:40]
        elif kind == "upper":
            name = name.upper()
        elif kind == "strip_accents":
            name = strip_accents(name)
        elif kind == "third_party_payer":
            pass                               # party substitution is done by the materialiser; the op is recorded
        else:
            raise ValueError(f"unknown name operator: {op!r}")
    return name
