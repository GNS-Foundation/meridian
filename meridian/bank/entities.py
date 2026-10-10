"""Virtual-bank entities (BANK-001). Pydantic v2; PUBLIC records vs answer key kept apart (BANK-002-16/17).
Monetary values are integer cents everywhere (BANK-001-08); every entity carries `episode` (BANK-001-14)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Sign = Literal["D", "C"]
HolderKind = Literal["person", "organisation"]
AccountStatus = Literal["open", "closed", "blocked"]
SequenceType = Literal["FRST", "RCUR", "OOFF", "FNAL"]
MandateStatus = Literal["active", "cancelled", "expired"]
CollectionState = Literal["presented", "settled", "rejected", "returned", "refunded", "reversed"]
RKind = Literal["reject", "return", "refund", "reversal"]
Initiator = Literal["debtor_psp", "creditor_psp", "csm", "creditor", "debtor"]
MavState = Literal["issued", "paid", "expired", "cancelled"]
PayingChannel = Literal["branch", "online", "other"]
MatchClass = Literal["one_to_one", "one_to_many", "many_to_one", "partial", "duplicate", "unmatched_noise"]
IntentKind = Literal["sct_in", "sct_out", "sdd_collect", "sdd_r", "mav_issue", "mav_pay", "fee"]


class Branch(BaseModel):
    cab: str
    label: str


class Bank(BaseModel):
    bank_id: str
    name: str
    abi: str
    bic: str
    country: str = "IT"
    branches: list[Branch] = Field(default_factory=list)
    sia_receiver: str = "A1B2C"            # SIA code of the receiving company on the CBI header (synthetic)
    episode: str = ""


class Holder(BaseModel):
    holder_id: str
    kind: HolderKind
    display_name: str
    fiscal_code_like: str                  # deliberately NOT a valid codice fiscale (D-11)
    address_label: str                     # fictional street label
    locality_label: str = ""               # fictional locality label (record 63 YYY pos. 81-120)
    episode: str = ""


class Account(BaseModel):
    account_id: str
    bank_id: str
    cab: str
    holder_id: str
    iban: str
    currency: str = "EUR"
    opened_on: str = "2026-01-05"
    account_type: str = "current"
    status: AccountStatus = "open"
    episode: str = ""


class Counterparty(BaseModel):
    name: str
    iban: str | None = None
    bic: str | None = None
    fiscal_code_like: str | None = None
    address_label: str | None = None
    locality_label: str | None = None
    holder_id: str | None = None           # when the counterparty is a holder of a virtual bank


class Movement(BaseModel):
    movement_id: str
    account_id: str
    booking_date: str
    value_date: str
    sign: Sign
    amount_cents: int = Field(ge=0)
    cbi_causale: str
    bank_reference: str = ""               # CRO/CRI-like, <= 16 chars (record 62 pos. 62-77)
    end_to_end_id: str = ""                # <= 35
    message_id: str = ""                   # <= 35
    remittance_unstructured: str = ""      # <= 140 (BANK-003-03)
    counterparty: Counterparty | None = None
    instrument_ref: str                    # BANK-001-16: never an orphan
    kind: IntentKind | Literal["sdd_settle", "sdd_r", "mav_pay", "fee"]
    cheque_number: str = ""                # mandatory iff cbi_causale == "13"
    customer_ref_type: str = ""            # record 62 pos. 78-86 keyword
    customer_ref_text: str = ""            # record 62 pos. 87-120
    order_date: str = ""                   # GGMMAAAA for 63 YYY
    r_reason_code: str = ""                # for SDD R movements (camt RtrInf)
    mandate_id: str = ""
    episode: str = ""


class Balance(BaseModel):
    account_id: str
    book_date: str
    opening_book: int
    closing_book: int
    closing_available: int | None = None
    currency: str = "EUR"


class Mandate(BaseModel):
    mandate_id: str
    creditor_id: str
    creditor_name: str
    creditor_account_id: str
    debtor_account_id: str
    debtor_name: str
    signed_on: str
    sequence_type: SequenceType = "FRST"
    status: MandateStatus = "active"
    last_collection_on: str | None = None
    episode: str = ""


class RTransaction(BaseModel):
    kind: RKind
    reason_code: str
    date: str
    initiator: Initiator
    amount_cents: int
    original_collection_id: str
    requested_reason_code: str | None = None     # BANK-003-18 substitution record


class Collection(BaseModel):
    collection_id: str
    mandate_id: str
    requested_collection_date: str
    settlement_date: str | None = None
    amount_cents: int
    end_to_end_id: str
    remittance_unstructured: str = ""
    state: CollectionState = "presented"
    r_transactions: list[RTransaction] = Field(default_factory=list)
    episode: str = ""


class MavNotice(BaseModel):
    mav_id: str
    creditor_account_id: str
    debtor_holder_id: str | None = None
    amount_cents: int
    due_date: str
    issued_on: str
    state: MavState = "issued"
    paid_on: str | None = None
    paid_amount_cents: int | None = None
    paying_channel: PayingChannel | None = None
    episode: str = ""


class Intent(BaseModel):
    """Generic unit of purpose returned by a Scenario (BANK-002-10)."""
    intent_id: str
    scenario_id: str
    kind: IntentKind
    when: str
    parties: dict = Field(default_factory=dict)
    amount_cents: int = 0
    remittance_clean: str = ""
    remittance_noise: list[str] = Field(default_factory=list)
    counterparty_name_noise: list[str] = Field(default_factory=list)
    expected_outcome: str = "settle"
    links: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)
