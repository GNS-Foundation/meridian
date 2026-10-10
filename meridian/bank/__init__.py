"""Meridian virtual bank — a deterministic, client-agnostic synthetic bank (spec/MERIDIAN-BANK-000..005).

Sub-package of the Meridian SIM (BANK-000-02). It computes NO reputation, imports nothing from aml/grafomem/cgr
(BANK-000-04), runs fully offline (BANK-000-05), uses no database (BANK-000-09) and no new runtime dependency.
Every writer cites its source and carries the `A-nn` assumptions it depends on (BANK-000-07).
"""
SPEC_VERSION = "BANK-000..005@420d95a"
# Digest of every file under spec/ at the commit named in SPEC_VERSION (tests/bank/test_spec_version.py). A content
# digest is used instead of `git log -- spec/` because the check must also work where there is no git history: shallow
# CI clones, sdists, and the downstream venv that installs this package from a commit. Recompute with `spec_digest()`.
SPEC_DIGEST = "sha256:2699caecc76f13432fac35a58fd45d27ace35dcc0cf8e7e1f375429c3eebb320"


def spec_digest(spec_dir) -> str:
    """sha256 over (relative path, bytes) of every file under `spec_dir`, sorted by path; stdlib only."""
    import hashlib
    from pathlib import Path as _P
    h = hashlib.sha256()
    for f in sorted(x for x in _P(spec_dir).rglob("*") if x.is_file()):
        h.update(f.relative_to(spec_dir).as_posix().encode()); h.update(b"\0"); h.update(f.read_bytes()); h.update(b"\0")
    return "sha256:" + h.hexdigest()
