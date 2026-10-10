"""pain.002.001.10 writer (BANK-004-50..52): one Customer Payment Status Report per rejected collection, emitted to the
creditor-side folder out/<episode>/pain002/<creditor_id>/. A-04: Core version by analogy with S5/S6. Rejects only
(D-16); OrgnlMsgNmId = pain.008.001.08."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from meridian.bank.clock import iso_dt
from meridian.bank.entities import Collection, Mandate
from meridian.bank.formats import Selection, cents, register
from meridian.bank.world import BankWorldView

NS = "urn:iso:std:iso:20022:tech:xsd:pain.002.001.10"


def render_reject(world: BankWorldView, coll: Collection, mandate: Mandate, seq: int) -> str:
    r = next(x for x in coll.r_transactions if x.kind == "reject")
    bank = world.banks[world.accounts[mandate.creditor_account_id].bank_id]
    debtor_iban = world.accounts[mandate.debtor_account_id].iban
    created = iso_dt(date.fromisoformat(r.date), 12)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{NS}">
  <CstmrPmtStsRpt>
    <GrpHdr><MsgId>{world.episode}-pain002-{seq:04d}</MsgId><CreDtTm>{created}</CreDtTm><InitgPty><Nm>{bank.name}</Nm></InitgPty></GrpHdr>
    <OrgnlGrpInfAndSts><OrgnlMsgId>{world.episode}-pain008-{seq:04d}</OrgnlMsgId><OrgnlMsgNmId>pain.008.001.08</OrgnlMsgNmId></OrgnlGrpInfAndSts>
    <OrgnlPmtInfAndSts>
      <OrgnlPmtInfId>{world.episode}-pmtinf-{seq:04d}</OrgnlPmtInfId>
      <TxInfAndSts>
        <StsId>{world.episode}-sts-{seq:04d}</StsId><OrgnlEndToEndId>{coll.end_to_end_id}</OrgnlEndToEndId><TxSts>RJCT</TxSts>
        <StsRsnInf><Rsn><Cd>{r.reason_code}</Cd></Rsn></StsRsnInf>
        <OrgnlTxRef><Amt><InstdAmt Ccy="EUR">{cents(coll.amount_cents)}</InstdAmt></Amt><MndtRltdInf><MndtId>{mandate.mandate_id}</MndtId></MndtRltdInf><DbtrAcct><Id><IBAN>{debtor_iban}</IBAN></Id></DbtrAcct></OrgnlTxRef>
      </TxInfAndSts>
    </OrgnlPmtInfAndSts>
  </CstmrPmtStsRpt>
</Document>
"""


@register
class Pain002Sink:
    format_id = "pain002"
    version = "pain.002.001.10"
    sources = ["S5", "S6", "S7"]
    assumptions = ["A-04"]

    def emit(self, world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]:
        out: list[Path] = []
        seq = selection.msg_seq
        for cid in sorted(world.collections):
            coll = world.collections[cid]
            if coll.state != "rejected":
                continue
            mandate = world.mandates[coll.mandate_id]
            p = out_dir / "pain002" / mandate.creditor_id / f"{cid}.pain002.xml"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(render_reject(world, coll, mandate, seq), encoding="utf-8")
            out.append(p); seq += 1
        return out
