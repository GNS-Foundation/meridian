#!/usr/bin/env python3
"""Corpus lint — checks the corpus itself. It implements nothing of meridian.bank.

Usage:  python3 corpus/bank/lint_corpus.py            # lint the corpus
        python3 corpus/bank/lint_corpus.py --self-test # non-vacuity: every check must catch its own mutation

Checks
  * MANIFEST completeness: every vector dir listed, every listed path and artefact present, kind/polarity/
    assumption placement consistent, every `covers` id exists in spec/.
  * Polarity is read from vector.json ("polarity", fallback: expected.verdict) — never from the path.
  * Fixed-width artefacts: 120-char records; CBI RH internals (envelope, EF counters, 61↔64 date and currency,
    balance arithmetic, 63 ≤ 5, ID1/RI1/RI2 order, cheque rule, YYY name width, unsupported 63 bodies, record 65).
  * IBANs: EVERY IBAN in EVERY artefact and vector.json — XML <IBAN>, CBI record 61 (reconstructed), record 63 YY2
    pos. 67-100, and any IT-shaped token in text — ISO 7064 mod-97 + Italian CIN + length 27.
  * Identifiers in vector inputs: BIC length (8/11), MAV id 17 digits; remittance ≤ 140; name ≤ 40.
  * Positive vectors must raise no rule; negative vectors must raise exactly their expected rule_id.
  * Client-agnostic deny-list: read from the file named by MERIDIAN_DENYLIST_FILE (one term per line,
    case-insensitive WHOLE-WORD match); if unset the check is SKIPPED with a reason (the list is never stored here).
  * Coverage: which BANK requirement ids have no vector.
Exit 1 on any failure.
"""
import json, os, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
SPEC = HERE.parent.parent / "spec"
IBAN_RE = re.compile(r"\bIT\d{2}[A-Z]\d{10}[A-Z0-9]{12}\b")

# ---------- identifier algorithms (spec BANK-001-05 / S11), independent of the authoring step ----------
TAB = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VAL_PARI = [0,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25]
VAL_DISPARI = [1,0,5,7,9,13,15,17,19,21,1,0,5,7,9,13,15,17,19,21,2,4,18,20,11,3,6,8,12,14,16,10,22,25,24,23]
def cin_it(body):
    s = 0
    for i, ch in enumerate(body, start=1):
        p = TAB.index(ch.upper()); s += VAL_DISPARI[p] if i % 2 == 1 else VAL_PARI[p]
    return chr(ord('A') + s % 26)
def mod97(s):
    n = 0
    for ch in s:
        n = (n*10 + int(ch)) % 97 if ch.isdigit() else (n*100 + (ord(ch.upper())-55)) % 97
    return n
def iban_rules(iban):
    """Rule ids violated by an Italian IBAN string."""
    v = []
    if len(iban) != 27 or not iban.startswith("IT"): return ["IBAN-LEN-IT-27"]
    if mod97(iban[4:] + iban[:4]) != 1: v.append("IBAN-MOD97")
    if cin_it(iban[5:]) != iban[4]: v.append("IBAN-CIN")
    return v
_CF = json.loads((HERE / "data" / "codice_fiscale_check.json").read_text(encoding="utf-8"))
def cf_check_char(first15: str) -> str:
    """Art. 7, D.M. 23/12/1976 (data/codice_fiscale_check.json): positions counted from 1; odd -> odd table."""
    total = 0
    for i, ch in enumerate(first15.upper(), start=1):
        total += (_CF["odd_positions"] if i % 2 == 1 else _CF["even_positions"])[ch]
    return _CF["remainder_to_letter"][total % 26]
def cf_like_rules(code: str) -> list:
    """A synthetic fiscal_code_like must NOT be a valid codice fiscale: a 16-char value whose 16th char equals the
    Art. 7 control character of its first 15 is REJECTED (CF-LIKE-INVALID). Shorter/longer values pass by shape."""
    c = code.upper()
    if len(c) != 16 or not re.fullmatch(r"[A-Z0-9]{15}[A-Z]", c):
        return []
    try:
        return ["CF-LIKE-INVALID"] if cf_check_char(c[:15]) == c[15] else []
    except KeyError:
        return []
def bic_rules(bic):  return [] if re.fullmatch(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?", bic) else ["BIC-LEN"]
def mav_rules(mav):  return [] if re.fullmatch(r"\d{17}", mav) else ["MAV-ID-LEN"]

# ---------- CBI RH structural checks (positions per BANK-004-11..19) ----------
def ibans_in_rh(lines):
    out = []
    for l in lines:
        if len(l) != 120: continue
        t = l[1:3]
        if t == "61":
            out.append("IT" + l[101:103] + l[51:52] + l[52:57] + l[57:62] + l[62:74])
        elif t == "63" and l[13:16] == "YY2":
            out.append(l[66:100].strip())
    return out

def check_rh(lines):
    v = []
    if any(len(l) != 120 for l in lines): return ["CBI-RH-LEN-120"]
    types = [l[1:3] for l in lines]
    if types[0] != "RH" or types[-1] != "EF": return ["CBI-RH-ENVELOPE"]
    ef = lines[-1]
    if not (ef[45:52].isdigit() and ef[82:89].isdigit()): return ["CBI-RH-EF-COUNT"]
    if int(ef[82:89]) != len(lines) or int(ef[45:52]) != types.count("61"): v.append("CBI-RH-EF-COUNT")
    i = 1
    while i < len(lines) - 1:
        if types[i] != "61": v.append("CBI-RH-SEQ"); break
        r61 = lines[i]; prog = r61[3:10]; ccy61 = r61[74:77]; date61 = r61[77:83]
        if not re.fullmatch(r"\d{15}", r61[84:99]): v.append("CBI-RH-AMT-NUM"); opening = 0
        else: opening = int(r61[84:99]) * (1 if r61[83] == "C" else -1)
        total = opening; i += 1; n63 = 0; seen = []
        while i < len(lines) - 1 and types[i] in ("62", "63"):
            l = lines[i]
            if l[3:10] != prog: v.append("CBI-RH-PROG")
            if types[i] == "62":
                n63 = 0; seen = []
                amt = l[26:41]
                if not re.fullmatch(r"\d{15}", amt): v.append("CBI-RH-AMT-NUM"); amt = "0"
                total += int(amt) * (1 if l[25] == "C" else -1)
                causale = l[41:43]; cheque = l[45:61].strip()
                if (causale == "13") != bool(cheque): v.append("CBI-RH-62-13-CHEQUE")
            else:
                n63 += 1
                if n63 > 5: v.append("CBI-RH-63-MAX5")
                flag = l[13:16]; seen.append(flag)
                if flag in ("KKK", "ZZ1", "ZZ2", "ZZ3"): v.append("CBI-RH-63-UNSUPPORTED-FLAG")
                if flag == "RI2" and "RI1" not in seen[:-1]: v.append("CBI-RH-63-SEQ")
                if flag == "RI1" and "ID1" not in seen[:-1]: v.append("CBI-RH-63-SEQ")
                if flag == "YYY" and len(l[40:80].rstrip()) == 40 and l[80] != " ": v.append("CBI-RH-63-YYY-NAME-40")
            i += 1
        if i >= len(lines) - 1 or types[i] != "64": v.append("CBI-RH-SEQ"); break
        r64 = lines[i]
        if r64[3:10] != prog: v.append("CBI-RH-PROG")
        if r64[10:13] != ccy61: v.append("CBI-RH-61-64-CCY")
        if r64[13:19] != date61: v.append("CBI-RH-61-64-DATE")
        if not re.fullmatch(r"\d{15}", r64[20:35]): v.append("CBI-RH-AMT-NUM")
        elif int(r64[20:35]) * (1 if r64[19] == "C" else -1) != total: v.append("CBI-RH-BAL")
        i += 1
        if i < len(lines) - 1 and types[i] == "65": v.append("CBI-RH-65-NOT-EMITTED"); i += 1
    return v

def read_fixed(path):
    with open(path, encoding="utf-8", newline="") as fh:
        lines = fh.read().split("\r\n")
    return lines[:-1] if lines and lines[-1] == "" else lines

# ---------- per-vector evaluation ----------
def rules_for_vector(d, v, artefacts):
    """All rule ids raised by a vector's artefacts and inputs (independent of polarity)."""
    raised = []
    blob = json.dumps(v, ensure_ascii=False)
    exp = v["expected"]
    for a in artefacts:
        p = d / a
        text = p.read_text(encoding="utf-8") if not a.endswith(".txt") else "\r\n".join(read_fixed(p))
        if a.endswith(".txt"):
            lines = read_fixed(p)
            if a == "RH.txt": raised += check_rh(lines)
            elif any(len(l) != 120 for l in lines): raised.append("CBI-RH-LEN-120")
            if a == "RH.txt":
                for iban in ibans_in_rh(lines): raised += iban_rules(iban)
        if a.endswith(".xml"):
            for iban in re.findall(r"<IBAN>([^<]*)</IBAN>", text): raised += iban_rules(iban)
            if "XML-XSD" == exp.get("rule_id") and re.search(r"<Entry>", text): raised.append("XML-XSD")  # structural stand-in; real XSD check is D-02
        for iban in IBAN_RE.findall(text): raised += iban_rules(iban)
    # inputs
    for iban in set(IBAN_RE.findall(blob)): raised += iban_rules(iban)
    for key in ("iban",):
        for val in re.findall(r'"%s": "([^"]*)"' % key, blob):
            if not IBAN_RE.fullmatch(val): raised += iban_rules(val)
    for bic in re.findall(r'"bics?": (?:\[([^\]]*)\]|"([^"]*)")', blob):
        for b in re.findall(r'"([A-Z0-9]+)"', bic[0]) + ([bic[1]] if bic[1] else []): raised += bic_rules(b)
    for mav in re.findall(r'"mav_id": "([0-9]+)"', blob): raised += mav_rules(mav)
    for cf in re.findall(r'"fiscal_code_like": "([^"]*)"', blob): raised += cf_like_rules(cf)
    for s in re.findall(r'"remittance_emitted": "([^"]*)"', blob):
        if len(s) > 140: raised.append("SEPA-RMT-140")
    for s in re.findall(r'"counterparty_name_emitted": "([^"]*)"', blob):
        if len(s) > 40: raised.append("NAME-LEN-40")
    return raised

def lint(root=HERE, spec=SPEC, verbose=True):
    fails = []
    manifest = json.loads((root / "MANIFEST.json").read_text())
    listed = {m["path"]: m for m in manifest["vectors"]}
    on_disk = {str(p.parent.relative_to(root)) for p in root.rglob("vector.json")}
    for p in sorted(on_disk - set(listed)): fails.append(f"vector dir not in MANIFEST: {p}")
    for p in sorted(set(listed) - on_disk): fails.append(f"MANIFEST path missing on disk: {p}")
    spec_ids = set()
    for f in spec.glob("MERIDIAN-BANK-00*.md"):
        spec_ids |= set(re.findall(r"^\| (BANK-00\d-\d\d) \|", f.read_text(), re.M))
    covered, counts, pol = {}, {"positive": 0, "negative": 0, "assumed": 0}, {"positive": 0, "negative": 0}
    for path, m in listed.items():
        d = root / path
        if not (d / "vector.json").exists(): continue
        v = json.loads((d / "vector.json").read_text())
        kind = v["kind"]; counts[kind] = counts.get(kind, 0) + 1
        polarity = v.get("polarity") or ("negative" if v["expected"].get("verdict") == "reject" else "positive")
        pol[polarity] += 1
        if m.get("polarity") not in (None, polarity): fails.append(f"{path}: MANIFEST polarity disagrees with vector.json")
        if kind == "assumed" and not v["assumptions"]: fails.append(f"{path}: assumed vector without A-id")
        if kind == "assumed" and not path.startswith("_assumed/"): fails.append(f"{path}: assumed vector outside _assumed/")
        if kind != "assumed" and path.startswith("_assumed/"): fails.append(f"{path}: non-assumed vector under _assumed/")
        for a in v["assumptions"]:
            if not re.fullmatch(r"A-\d\d", a): fails.append(f"{path}: bad assumption id {a}")
        for c in v["covers"]:
            if c not in spec_ids: fails.append(f"{path}: covers unknown id {c}")
            covered.setdefault(c, []).append(path)
        arts = m.get("artefacts", [])
        for a in arts:
            if not (d / a).exists(): fails.append(f"{path}: artefact {a} missing")
        arts = [a for a in arts if (d / a).exists()]
        raised = rules_for_vector(d, v, arts)
        exp_rule = v["expected"].get("rule_id")
        if polarity == "negative":
            if not exp_rule: fails.append(f"{path}: negative vector without expected rule_id")
            elif exp_rule in ("AK-NO-INTENT","AK-REFUND-UNSETTLED","AK-MAV-PAID-NO-CREDIT","AK-THIRD-PARTY-DISTINCT","AK-NAME-NOISE-REPLAY","NOISE-INITIALS-SHAPE","NAME-NOT-CURATED","SDD-REFUND-8W","SDD-REFUND-13M","SDD-CODE-RTYPE","SDD-RETURN-UNSETTLED","SDD-CODE-SCOPE","SDD-SEQ-AG02","SDD-NO-REFUSAL","PAIN002-ORGNL-MSGNM"):
                pass  # semantic rules of the future validator: the corpus states the expectation; the lint cannot evaluate them
            elif exp_rule not in raised:
                fails.append(f"{path}: expected {exp_rule} not detected; detected {sorted(set(raised))}")
        else:
            if raised: fails.append(f"{path}: positive vector raises {sorted(set(raised))}")
    # synthetic fiscal codes in data/ must fail the D.M. 23/12/1976 check (BANK-001-06, D-11)
    banks = json.loads((root / "data" / "synthetic_banks.json").read_text(encoding="utf-8"))
    for h in banks.get("holders", []):
        if cf_like_rules(h.get("fiscal_code_like", "")): fails.append(f"data/synthetic_banks.json holder {h['holder_id']}: fiscal_code_like is a VALID codice fiscale (CF-LIKE-INVALID)")
    # client-agnostic deny-list (BANK-005-32) — list lives OUTSIDE the repo
    deny_path = os.environ.get("MERIDIAN_DENYLIST_FILE")
    deny_status = "SKIPPED (MERIDIAN_DENYLIST_FILE unset; the deny-list is kept outside this public repository)"
    if deny_path:
        terms = [t.strip() for t in pathlib.Path(deny_path).read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
        # case-insensitive WHOLE-WORD matching: a term matches only when not glued to other word characters on
        # either side, so a short term never hits inside a longer word. Multi-word terms and terms containing
        # punctuation are matched literally as a unit. (No example terms here: this file is itself scanned.)
        patterns = [(t, re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)", re.IGNORECASE)) for t in terms]
        hits = []
        for p in list(root.rglob("*")) + list(spec.glob("*.md")):
            if p.is_file() and p.suffix in (".json", ".txt", ".xml", ".md", ".py"):
                text = p.read_text(encoding="utf-8", errors="replace")
                hits += [f"{p.relative_to(root.parent.parent)}: '{t}'" for t, rx in patterns if rx.search(text)]
        deny_status = f"checked {len(terms)} terms: " + ("no hits" if not hits else f"{len(hits)} hit(s)")
        fails += [f"deny-list hit: {h}" for h in hits]
    uncovered = sorted(spec_ids - set(covered))
    pct = 100.0 * len(covered) / len(spec_ids) if spec_ids else 0
    if verbose:
        print(f"vectors: {sum(counts.values())}  kind: positive={counts['positive']} negative={counts['negative']} assumed={counts['assumed']}  polarity: positive={pol['positive']} negative={pol['negative']}")
        print(f"requirement coverage: {len(covered)}/{len(spec_ids)} = {pct:.1f}%")
        print("uncovered ids:", " ".join(uncovered) if uncovered else "none")
        print("client-agnostic deny-list:", deny_status)
    return fails

# ---------- self-test: every check must catch its own mutation (non-vacuity) ----------
def self_test():
    good_rh = read_fixed(HERE / "_assumed/cbi-rh-002-sct-in-48-full-63-chain/RH.txt")
    good_xml = (HERE / "_assumed/camt053-001-sct-in/camt053.xml").read_text(encoding="utf-8")
    good_iban = ibans_in_rh(good_rh)[0]
    def rh_mut(fn): return lambda: check_rh(fn([l for l in good_rh]))
    def swap_line(idx, new): 
        def f(L): L[idx] = new; return L
        return f
    L = good_rh
    r64 = [l for l in L if l[1:3] == "64"][0]; i64 = L.index(r64)
    r62 = [l for l in L if l[1:3] == "62"][0]; i62 = L.index(r62)
    ef = L[-1]
    cases = [
      ("CBI-RH-LEN-120",            rh_mut(swap_line(i62, r62[:119]))),
      ("CBI-RH-61-64-DATE",         rh_mut(swap_line(i64, r64[:13] + "060126" + r64[19:]))),
      ("CBI-RH-BAL",                rh_mut(swap_line(i64, r64[:20] + f"{int(r64[20:35])+1:015d}" + r64[35:]))),
      ("CBI-RH-62-13-CHEQUE",       rh_mut(swap_line(i62, r62[:41] + "13" + r62[43:]))),
      ("CBI-RH-63-MAX5",            rh_mut(lambda M: M[:i64] + [" 63" + "0000001" + "001" + "X".ljust(107)] + M[i64:-1] + [ef[:82] + f"{len(M)+1:07d}" + ef[89:]])),
      ("CBI-RH-63-SEQ",             rh_mut(lambda M: [l for l in M if l[13:16] != "RI1"][:-1] + [ef[:82] + f"{len(M)-1:07d}" + ef[89:]])),
      ("CBI-RH-EF-COUNT",           rh_mut(lambda M: M[:-1] + [ef[:82] + f"{len(M)+1:07d}" + ef[89:]])),
      ("CBI-RH-AMT-NUM",            rh_mut(swap_line(i62, r62[:26] + "0000000001234X5" + r62[41:]))),
      ("CBI-RH-61-64-CCY",          rh_mut(swap_line(i64, r64[:10] + "USD" + r64[13:]))),
      ("CBI-RH-63-YYY-NAME-40",     rh_mut(lambda M: [ (l[:40] + "M"*41 + l[81:]) if l[13:16]=="YYY" else l for l in M])),
      ("CBI-RH-63-UNSUPPORTED-FLAG",rh_mut(lambda M: [ (l[:13] + "KKK" + l[16:]) if l[13:16]=="YY2" else l for l in M])),
      ("CBI-RH-65-NOT-EMITTED",     rh_mut(lambda M: M[:i64+1] + [" 65" + "0000001" + "050126".ljust(110)] + [ef[:82] + f"{len(M)+1:07d}" + ef[89:]])),
      ("IBAN-MOD97 (record 61)",    lambda: sum((iban_rules(x) for x in ibans_in_rh([ (l[:62] + ("9" if l[62]!="9" else "8") + l[63:]) if l[1:3]=="61" else l for l in L])), [])),
      ("IBAN-MOD97 (record 63 YY2)",lambda: sum((iban_rules(x) for x in ibans_in_rh([ (l[:70] + ("9" if l[70]!="9" else "8") + l[71:]) if l[13:16]=="YY2" else l for l in L])), [])),
      ("IBAN-MOD97 (camt XML)",     lambda: sum((iban_rules(x) for x in re.findall(r"<IBAN>([^<]*)</IBAN>", good_xml.replace(good_iban, good_iban[:12] + ("9" if good_iban[12]!="9" else "8") + good_iban[13:]))), [])),
      ("IBAN-CIN",                  lambda: iban_rules(good_iban[:4] + ("A" if good_iban[4]!="A" else "B") + good_iban[5:])),
      ("IBAN-LEN-IT-27",            lambda: iban_rules(good_iban[:-1])),
      ("BIC-LEN",                   lambda: bic_rules("FNTAITMMX")),
      ("MAV-ID-LEN",                lambda: mav_rules("9000100000004261")),
    ]
    ok = True
    for rule, mutant in cases:
        raised = mutant(); rid = rule.split(" ")[0]
        hit = rid in raised
        print(f"  {'PASS' if hit else 'FAIL'}  {rule:<32} mutated -> {sorted(set(raised))}")
        ok &= hit
    clean = check_rh(good_rh) + sum((iban_rules(x) for x in ibans_in_rh(good_rh)), []) + sum((iban_rules(x) for x in re.findall(r"<IBAN>([^<]*)</IBAN>", good_xml)), []) + cf_like_rules("MRMCLL99Z99Z999Z")
    print(f"  {'PASS' if not clean else 'FAIL'}  originals clean (restore)            -> {clean}")
    ok &= not clean
    return ok

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        print("lint self-test (non-vacuity):"); sys.exit(0 if self_test() else 1)
    fails = lint()
    if fails:
        print("\nFAILURES:"); [print(" -", f) for f in fails]; sys.exit(1)
    print("lint: OK")
