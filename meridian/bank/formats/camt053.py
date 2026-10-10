"""camt.053.001.08 writer (BANK-004-40/41). A-06: version choice pending EPC188-09 v5.0. Element names follow ISO 20022
as known to the author; XSD validation is the implementation test's job (BANK-004-44, D-02). BkTxCd values are
placeholders pending D-15 (PMNT/RCDT/ESCT for inbound SCT, PMNT/IDDT/RRTN for SDD returns)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from meridian.bank.clock import iso_dt
from meridian.bank.entities import Movement
from meridian.bank.formats import Selection, cents, register
from meridian.bank.world import BankWorldView

NS053 = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"
NS054 = "urn:iso:std:iso:20022:tech:xsd:camt.054.001.08"


def entry_xml(m: Movement) -> str:
    ind = "CRDT" if m.sign == "C" else "DBIT"
    head = f"""      <Ntry>
        <Amt Ccy="EUR">{cents(m.amount_cents)}</Amt><CdtDbtInd>{ind}</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts>
        <BookgDt><Dt>{m.booking_date}</Dt></BookgDt><ValDt><Dt>{m.value_date}</Dt></ValDt>
"""
    if m.kind == "sdd_r":
        return head + f"""        <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>IDDT</Cd><SubFmlyCd>RRTN</SubFmlyCd></Fmly></Domn></BkTxCd>
        <NtryDtls><TxDtls>
          <Refs><EndToEndId>{m.end_to_end_id}</EndToEndId><MndtId>{m.mandate_id}</MndtId></Refs>
          <RtrInf><OrgnlBkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>IDDT</Cd><SubFmlyCd>ESDD</SubFmlyCd></Fmly></Domn></OrgnlBkTxCd><Rsn><Cd>{m.r_reason_code}</Cd></Rsn></RtrInf>
        </TxDtls></NtryDtls>
      </Ntry>
"""
    cp = m.counterparty
    parties = ""
    if cp is not None and m.sign == "C":
        parties = f"          <RltdPties><Dbtr><Pty><Nm>{cp.name}</Nm></Pty></Dbtr>" + (f"<DbtrAcct><Id><IBAN>{cp.iban}</IBAN></Id></DbtrAcct>" if cp.iban else "") + "</RltdPties>\n"
    elif cp is not None:
        parties = f"          <RltdPties><Cdtr><Pty><Nm>{cp.name}</Nm></Pty></Cdtr>" + (f"<CdtrAcct><Id><IBAN>{cp.iban}</IBAN></Id></CdtrAcct>" if cp.iban else "") + "</RltdPties>\n"
    fam = ("RCDT", "ESCT") if m.sign == "C" else ("ICDT", "ESCT")
    if m.kind == "sdd_settle":
        fam = ("IDDT", "ESDD") if m.sign == "D" else ("RDDT", "ESDD")
    refs = f"<EndToEndId>{m.end_to_end_id}</EndToEndId>" if m.end_to_end_id else ""
    if m.mandate_id:
        refs += f"<MndtId>{m.mandate_id}</MndtId>"
    rmt = f"          <RmtInf><Ustrd>{m.remittance_unstructured}</Ustrd></RmtInf>\n" if m.remittance_unstructured else ""
    return head + f"""        <AcctSvcrRef>{m.bank_reference}</AcctSvcrRef>
        <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>{fam[0]}</Cd><SubFmlyCd>{fam[1]}</SubFmlyCd></Fmly></Domn></BkTxCd>
        <NtryDtls><TxDtls>
          <Refs>{refs}</Refs>
{parties}{rmt}        </TxDtls></NtryDtls>
      </Ntry>
"""


def render_statement(world: BankWorldView, account_id: str, book: date, msg_seq: int) -> str:
    acct = world.accounts[account_id]
    bal = world.balances[(account_id, book.isoformat())]
    created = iso_dt(book, 18)
    entries = "".join(entry_xml(m) for m in world.movements_by_account_day(account_id, book.isoformat()))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{NS053}">
  <BkToCstmrStmt>
    <GrpHdr><MsgId>{world.episode}-camt053-{msg_seq:04d}</MsgId><CreDtTm>{created}</CreDtTm></GrpHdr>
    <Stmt>
      <Id>{world.episode}-stmt-{account_id}-{book.strftime('%Y%m%d')}</Id><ElctrncSeqNb>{msg_seq}</ElctrncSeqNb><CreDtTm>{created}</CreDtTm>
      <Acct><Id><IBAN>{acct.iban}</IBAN></Id><Ccy>{acct.currency}</Ccy></Acct>
      <Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{cents(abs(bal.opening_book))}</Amt><CdtDbtInd>{"CRDT" if bal.opening_book >= 0 else "DBIT"}</CdtDbtInd><Dt><Dt>{book.isoformat()}</Dt></Dt></Bal>
      <Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{cents(abs(bal.closing_book))}</Amt><CdtDbtInd>{"CRDT" if bal.closing_book >= 0 else "DBIT"}</CdtDbtInd><Dt><Dt>{book.isoformat()}</Dt></Dt></Bal>
{entries}    </Stmt>
  </BkToCstmrStmt>
</Document>
"""


@register
class Camt053Sink:
    format_id = "camt053"
    version = "camt.053.001.08"
    sources = ["S9", "S10"]
    assumptions = ["A-06"]

    def emit(self, world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]:
        out: list[Path] = []
        seq = selection.msg_seq
        dates = selection.dates or [d.isoformat() for d in world.days]
        for acct_id in sorted(selection.account_ids or world.accounts):
            for d in dates:
                book = date.fromisoformat(d)
                if (acct_id, d) not in world.balances:
                    continue
                p = out_dir / "camt053" / f"{acct_id}_{book.strftime('%Y%m%d')}.camt053.xml"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(render_statement(world, acct_id, book, seq), encoding="utf-8")
                out.append(p); seq += 1
        return out
