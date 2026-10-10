"""CBI RH writer — CBI-RND-001 v6.05 (S1) as transcribed in BANK-004-10..23. One flow per bank per book date:
RH, then per account 61 / 62* / 63* / 64, then EF. Records 120 chars, CR LF (BANK-004-03). Amounts: integer cents
(A-01). RI1 extent per the S1 table (A-10)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from meridian.bank.clock import ggmmaa
from meridian.bank.entities import Movement
from meridian.bank.formats import Selection, register
from meridian.bank.world import BankWorldView


def rec(fields: list[tuple[int, int, str, str]]) -> str:
    line = [" "] * 120
    for a, b, val, kind in fields:
        w = b - a + 1
        s = str(val).rjust(w, "0") if kind == "n" else str(val).ljust(w)
        if len(s) != w:
            raise ValueError(f"field {a}-{b} does not fit: {val!r}")
        line[a - 1:b] = list(s)
    return "".join(line)


def r_header(abi: str, sia: str, created: date, support: str) -> str:
    return rec([(2, 3, "RH", "an"), (4, 8, abi, "n"), (9, 13, sia, "an"), (14, 19, ggmmaa(created), "n"), (20, 39, support, "an")])


def r_trailer(abi: str, sia: str, created: date, support: str, n_statements: int, n_records: int) -> str:
    return rec([(2, 3, "EF", "an"), (4, 8, abi, "n"), (9, 13, sia, "an"), (14, 19, ggmmaa(created), "n"), (20, 39, support, "an"),
                (46, 52, n_statements, "n"), (83, 89, n_records, "n")])


def r61(prog: int, iban: str, opening: int, book: date, currency: str = "EUR", causale: str = "93001") -> str:
    return rec([(2, 3, "61", "an"), (4, 10, prog, "n"), (29, 33, causale, "n"), (52, 52, iban[4], "an"), (53, 57, iban[5:10], "n"), (58, 62, iban[10:15], "n"),
                (63, 74, iban[15:27], "an"), (75, 77, currency, "an"), (78, 83, ggmmaa(book), "n"), (84, 84, "C" if opening >= 0 else "D", "an"),
                (85, 99, abs(opening), "n"), (100, 101, "IT", "an"), (102, 103, iban[2:4], "n")])


def r62(prog: int, pm: int, m: Movement) -> str:
    return rec([(2, 3, "62", "an"), (4, 10, prog, "n"), (11, 13, pm, "n"), (14, 19, ggmmaa(date.fromisoformat(m.value_date)), "n"),
                (20, 25, ggmmaa(date.fromisoformat(m.booking_date)), "n"), (26, 26, m.sign, "an"), (27, 41, m.amount_cents, "n"), (42, 43, m.cbi_causale, "an"),
                (46, 61, m.cheque_number, "an"), (62, 77, m.bank_reference, "an"), (78, 86, m.customer_ref_type, "an"), (87, 120, m.customer_ref_text[:34], "an")])


def r63(prog: int, pm: int, flag: str, body: list[tuple[int, int, str, str]]) -> str:
    return rec([(2, 3, "63", "an"), (4, 10, prog, "n"), (11, 13, pm, "n"), (14, 16, flag, "an")] + body)


def r64(prog: int, closing: int, book: date, currency: str = "EUR") -> str:
    return rec([(2, 3, "64", "an"), (4, 10, prog, "n"), (11, 13, currency, "an"), (14, 19, ggmmaa(book), "n"), (20, 20, "C" if closing >= 0 else "D", "an"), (21, 35, abs(closing), "n")])


def records_63(prog: int, pm: int, m: Movement) -> list[str]:
    """BANK-003-06 / BANK-004-16/17: inbound 48 -> YYY, YY2, ID1(e2e), RI1(+RI2); outbound 26 -> ID1(message id); else none."""
    out: list[str] = []
    if m.cbi_causale == "48":
        cp = m.counterparty
        out.append(r63(prog, pm, "YYY", [(17, 24, m.order_date, "n"), (25, 40, (cp.fiscal_code_like or "")[:16] if cp else "", "an"),
                                         (41, 80, (cp.name.upper() if cp else "")[:40], "an"), (81, 120, (cp.locality_label or "")[:40] if cp else "", "an")]))
        if cp and (cp.address_label or cp.iban):
            out.append(r63(prog, pm, "YY2", [(17, 66, (cp.address_label or "")[:50], "an"), (67, 100, cp.iban or "", "an")]))
        out.append(r63(prog, pm, "ID1", [(52, 86, m.end_to_end_id, "an")]))
        rem = m.remittance_unstructured
        if rem:
            out.append(r63(prog, pm, "RI1", [(17, 120, rem[:104], "an")]))
            if len(rem) > 104:
                out.append(r63(prog, pm, "RI2", [(17, 52, rem[104:140], "an")]))
    elif m.cbi_causale == "26":
        out.append(r63(prog, pm, "ID1", [(17, 51, m.message_id, "an")] + ([(52, 86, m.end_to_end_id, "an")] if m.end_to_end_id else [])))
    if len(out) > 5:
        raise ValueError("more than five record 63 for one movement")
    return out


def render_flow(world: BankWorldView, bank_id: str, book: date, account_ids: list[str], support: str) -> str:
    bank = world.banks[bank_id]
    lines = [r_header(bank.abi, bank.sia_receiver, book, support)]
    n_stmt = 0
    for prog, acct_id in enumerate(account_ids, start=1):
        acct = world.accounts[acct_id]
        bal = world.balances.get((acct_id, book.isoformat()))
        if bal is None:
            continue
        n_stmt += 1
        lines.append(r61(prog, acct.iban, bal.opening_book, book, acct.currency))
        movs = world.movements_by_account_day(acct_id, book.isoformat())
        for pm, m in enumerate(movs, start=1):
            pm_wrapped = (pm - 1) % 999 + 1
            lines.append(r62(prog, pm_wrapped, m))
            lines.extend(records_63(prog, pm_wrapped, m))
        lines.append(r64(prog, bal.closing_book, book, acct.currency))
    lines.append(r_trailer(bank.abi, bank.sia_receiver, book, support, n_stmt, len(lines) + 1))
    return "\r\n".join(lines) + "\r\n"


@register
class CbiRhSink:
    format_id = "cbi-rh"
    version = "CBI-RND-001 v6.05"
    sources = ["S1"]
    assumptions = ["A-01", "A-10"]

    def emit(self, world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]:
        out: list[Path] = []
        dates = selection.dates or [d.isoformat() for d in world.days]
        for bank_id in sorted(world.banks):
            accts = sorted(a for a, acc in world.accounts.items() if acc.bank_id == bank_id and (not selection.account_ids or a in selection.account_ids))
            if not accts:
                continue
            for i, d in enumerate(dates, start=1):
                book = date.fromisoformat(d)
                support = selection.support_name or f"{world.episode}-{bank_id}-{book.strftime('%Y%m%d')}"[:20]
                text = render_flow(world, bank_id, book, accts, support)
                p = out_dir / "cbi-rh" / f"{bank_id}_{book.strftime('%Y%m%d')}.RH.txt"
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="latin-1", newline="") as fh:
                    fh.write(text)
                out.append(p)
        return out
