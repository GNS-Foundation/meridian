"""OutputSink protocol (BANK-004-01/02): writers are pure (world view in, files out), registered by format id,
each declaring `sources` (spec/README.md register ids) and `assumptions` (A-ids)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from meridian.bank.world import BankWorldView


@dataclass
class Selection:
    account_ids: list[str] | None = None
    dates: list[str] | None = None
    support_name: str | None = None           # CBI header "nome supporto" override (default: episode-derived)
    msg_seq: int = 1                           # first message sequence number for XML ids
    credits_only: bool = True                  # camt.054 default subset (BANK-004-42)


@runtime_checkable
class OutputSink(Protocol):
    format_id: str
    version: str
    sources: list[str]
    assumptions: list[str]

    def emit(self, world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]: ...


def cents(amount: int) -> str:
    return f"{amount // 100}.{amount % 100:02d}"


REGISTRY: dict[str, type] = {}


def register(cls):
    REGISTRY[cls.format_id] = cls
    return cls


from meridian.bank.formats import camt053, camt054, cbi_im, cbi_rh, pain002  # noqa: E402,F401  (populates REGISTRY)
