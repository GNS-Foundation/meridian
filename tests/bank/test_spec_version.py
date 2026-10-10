"""SPEC_VERSION names the commit the implementation was built against; SPEC_DIGEST pins the content of spec/ at that
commit. Editing anything under spec/ without bumping both constants fails here. This check runs in this repository only
(clone, CI, sdist): the wheel ships `meridian/` alone, so spec/ is absent from a downstream venv and the digest cannot be
recomputed there. Downstream verifies the installed commit (direct_url.json) plus SPEC_VERSION; this test guarantees
that SPEC_VERSION is honest about the spec it names. Content digest, not `git log`, so it also runs without history."""
from __future__ import annotations

import re
from pathlib import Path

from meridian.bank import SPEC_DIGEST, SPEC_VERSION, spec_digest

SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"


def test_spec_version_shape():
    assert re.fullmatch(r"BANK-000\.\.005@[0-9a-f]{7,40}", SPEC_VERSION)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", SPEC_DIGEST)


def test_spec_files_unchanged_since_named_commit():
    assert SPEC_DIR.is_dir() and any(SPEC_DIR.glob("MERIDIAN-BANK-*.md"))
    actual = spec_digest(SPEC_DIR)
    assert actual == SPEC_DIGEST, (
        f"spec/ changed after commit {SPEC_VERSION.split('@')[1]}: digest {actual} != {SPEC_DIGEST}. "
        "Bump SPEC_VERSION to the new commit and SPEC_DIGEST to this digest in meridian/bank/__init__.py.")


def test_probe_spec_edit_is_detected(tmp_path):
    """Non-vacuity: a copy of spec/ with one byte changed must produce a different digest; the untouched copy must not."""
    import shutil
    copy = tmp_path / "spec"; shutil.copytree(SPEC_DIR, copy)
    assert spec_digest(copy) == SPEC_DIGEST
    f = next(copy.glob("MERIDIAN-BANK-001-*.md"))
    f.write_bytes(f.read_bytes() + b" ")
    assert spec_digest(copy) != SPEC_DIGEST
    f.write_bytes(f.read_bytes()[:-1])
    assert spec_digest(copy) == SPEC_DIGEST
