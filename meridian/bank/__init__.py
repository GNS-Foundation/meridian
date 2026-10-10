"""Meridian virtual bank — a deterministic, client-agnostic synthetic bank (spec/MERIDIAN-BANK-000..005).

Sub-package of the Meridian SIM (BANK-000-02). It computes NO reputation, imports nothing from aml/grafomem/cgr
(BANK-000-04), runs fully offline (BANK-000-05), uses no database (BANK-000-09) and no new runtime dependency.
Every writer cites its source and carries the `A-nn` assumptions it depends on (BANK-000-07).
"""
SPEC_VERSION = "BANK-000..005@fc545ac"
