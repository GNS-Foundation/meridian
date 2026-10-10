"""CBI IM writer (MAV outcomes) — ENTIRE LAYOUT ASSUMED (A-02): CBI-MAV-001 not sourced. Structure borrowed from the
CBI-RIB-001 v6.02 return flow (S2): header IM, 7 records 14/20/30/40/50/51/70, trailer EF, 120 chars. Field positions
are placeholders mirroring corpus/bank/_assumed/cbi-im-001. Refuses to run without --allow-assumed-layouts (BANK-004-30)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from meridian.bank.clock import ggmmaa
from meridian.bank.formats import Selection, register
from meridian.bank.formats.cbi_rh import rec
from meridian.bank.world import BankWorldView


class AssumedLayoutRefused(RuntimeError):
    pass


def render_im(world: BankWorldView, bank_id: str, created: date, support: str, mav_ids: list[str]) -> str:
    bank = world.banks[bank_id]
    lines = [rec([(2, 3, "IM", "an"), (4, 8, bank.abi, "n"), (9, 13, bank.sia_receiver, "an"), (14, 19, ggmmaa(created), "n"), (20, 39, support, "an")])]
    n = 0
    for prog, mid in enumerate(mav_ids, start=1):
        notice = world.mav_notices[mid]
        if notice.state != "paid":
            continue
        n += 1
        acct = world.accounts[notice.creditor_account_id]
        creditor = world.holders[acct.holder_id]
        debtor = world.holders[notice.debtor_holder_id] if notice.debtor_holder_id else None
        paid = date.fromisoformat(notice.paid_on)
        lines += [
            rec([(2, 3, "14", "an"), (4, 10, prog, "n"), (23, 28, ggmmaa(paid), "n"), (29, 33, "30010", "n"), (34, 46, notice.paid_amount_cents, "n"), (47, 47, "-", "an"), (48, 48, "E", "an")]),
            rec([(2, 3, "20", "an"), (4, 10, prog, "n"), (11, 70, creditor.display_name.upper()[:60], "an")]),
            rec([(2, 3, "30", "an"), (4, 10, prog, "n"), (11, 70, (debtor.display_name.upper() if debtor else "")[:60], "an")]),
            rec([(2, 3, "40", "an"), (4, 10, prog, "n"), (11, 70, (f"{debtor.address_label} {debtor.locality_label}".upper() if debtor else "")[:60], "an")]),
            rec([(2, 3, "50", "an"), (4, 10, prog, "n"), (11, 90, f"MAV {mid} PAGATO {(notice.paying_channel or '').upper()} {paid.strftime('%d/%m/%Y')}"[:80], "an")]),
            rec([(2, 3, "51", "an"), (4, 10, prog, "n"), (11, 27, mid, "an")]),
            rec([(2, 3, "70", "an"), (4, 10, prog, "n")]),
        ]
    lines.append(rec([(2, 3, "EF", "an"), (4, 8, bank.abi, "n"), (9, 13, bank.sia_receiver, "an"), (14, 19, ggmmaa(created), "n"), (20, 39, support, "an"), (46, 52, n, "n"), (83, 89, len(lines) + 1, "n")]))
    return "\r\n".join(lines) + "\r\n"


@register
class CbiImSink:
    format_id = "cbi-im"
    version = "CBI-MAV-001 (ASSUMED, A-02)"
    sources = ["S3", "S2"]
    assumptions = ["A-02", "A-03", "A-01"]
    allow_assumed_layouts = False

    def emit(self, world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]:
        if not self.allow_assumed_layouts:
            raise AssumedLayoutRefused("cbi-im layout is ASSUMPTION A-02: pass --allow-assumed-layouts to emit it (BANK-004-30)")
        out: list[Path] = []
        for bank_id in sorted(world.banks):
            mav_ids = sorted(m for m, n in world.mav_notices.items() if world.accounts[n.creditor_account_id].bank_id == bank_id and n.state == "paid")
            if not mav_ids:
                continue
            created = world.days[-1]
            support = selection.support_name or f"{world.episode}-{bank_id}-IM"[:20]
            p = out_dir / "cbi-im" / f"{bank_id}_{created.strftime('%Y%m%d')}.IM.txt"
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="latin-1", newline="") as fh:
                fh.write(render_im(world, bank_id, created, support, mav_ids))
            out.append(p)
        return out
