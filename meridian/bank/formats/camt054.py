"""camt.054.001.08 writer (BANK-004-42/43): one notification per account per day for the selected subset (default
credits; SDD R-entries always included), same TxDtls shape as camt.053, no balances. A-06 as camt.053."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from meridian.bank.clock import iso_dt
from meridian.bank.formats import Selection, register
from meridian.bank.formats.camt053 import NS054, entry_xml
from meridian.bank.world import BankWorldView


def render_notification(world: BankWorldView, account_id: str, book: date, msg_seq: int, credits_only: bool = True) -> str:
    acct = world.accounts[account_id]
    created = iso_dt(book, 18)
    movs = [m for m in world.movements_by_account_day(account_id, book.isoformat()) if m.kind == "sdd_r" or not credits_only or m.sign == "C"]
    entries = "".join(entry_xml(m) for m in movs)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{NS054}">
  <BkToCstmrDbtCdtNtfctn>
    <GrpHdr><MsgId>{world.episode}-camt054-{msg_seq:04d}</MsgId><CreDtTm>{created}</CreDtTm></GrpHdr>
    <Ntfctn>
      <Id>{world.episode}-ntfctn-{account_id}-{book.strftime('%Y%m%d')}</Id><CreDtTm>{created}</CreDtTm>
      <Acct><Id><IBAN>{acct.iban}</IBAN></Id><Ccy>{acct.currency}</Ccy></Acct>
{entries}    </Ntfctn>
  </BkToCstmrDbtCdtNtfctn>
</Document>
"""


@register
class Camt054Sink:
    format_id = "camt054"
    version = "camt.054.001.08"
    sources = ["S9", "S10"]
    assumptions = ["A-06"]

    def emit(self, world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]:
        out: list[Path] = []
        seq = selection.msg_seq
        dates = selection.dates or [d.isoformat() for d in world.days]
        for acct_id in sorted(selection.account_ids or world.accounts):
            for d in dates:
                book = date.fromisoformat(d)
                if not world.movements_by_account_day(acct_id, d):
                    continue
                p = out_dir / "camt054" / f"{acct_id}_{book.strftime('%Y%m%d')}.camt054.xml"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(render_notification(world, acct_id, book, seq, selection.credits_only), encoding="utf-8")
                out.append(p); seq += 1
        return out
