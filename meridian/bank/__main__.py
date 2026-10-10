"""CLI: python -m meridian.bank (BANK-000-05: offline; D-07). The default episode name is the ONLY place a wall-clock
value may appear (BANK-005-12 allow-list)."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from meridian.bank.answer_key import write_answer_key
from meridian.bank.formats import REGISTRY, Selection
from meridian.bank.generator import BankConfig, generate_world, generator_block
from meridian.bank.scenarios import BUILTIN, load_scenario


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m meridian.bank", description="Meridian virtual bank — deterministic synthetic bank files (spec BANK-000..005).")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--episode", default=None, help="namespace for ids (default: fresh, idempotent)")
    ap.add_argument("--start-date", default=None, help="ISO date; default 2026-01-05 (sim epoch)")
    ap.add_argument("--banks", type=int, default=2)
    ap.add_argument("--accounts", type=int, default=50)
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--sct-per-day-per-account", type=float, default=0.6)
    ap.add_argument("--sdd-mandates", type=int, default=30)
    ap.add_argument("--mav-notices", type=int, default=40)
    ap.add_argument("--mav-paid-rate", type=float, default=0.85)
    ap.add_argument("--scenario", action="append", default=None, help=f"built-in id {sorted(BUILTIN)}, entry-point name, or pkg.module:Class (repeatable)")
    ap.add_argument("--format", default="cbi-rh,camt053,camt054,pain002", help=f"comma list of {sorted(REGISTRY)}")
    ap.add_argument("--out", default="out")
    ap.add_argument("--episodes-dir", default="episodes")
    ap.add_argument("--allow-assumed-layouts", action="store_true", help="also allow writers whose layout is an ASSUMPTION (cbi-im, A-02)")
    ap.add_argument("--describe-formats", action="store_true")
    args = ap.parse_args(argv)

    if args.describe_formats:
        for fid, cls in sorted(REGISTRY.items()):
            print(json.dumps({"format_id": fid, "version": cls.version, "sources": cls.sources, "assumptions": cls.assumptions}))
        return
    episode = args.episode or f"s{args.seed}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"   # allow-listed wall clock
    cfg = BankConfig(seed=args.seed, episode=episode, start_date=date.fromisoformat(args.start_date) if args.start_date else BankConfig.model_fields["start_date"].default,
                     banks=args.banks, accounts=args.accounts, days=args.days, sct_per_day_per_account=args.sct_per_day_per_account, sdd_mandates=args.sdd_mandates,
                     mav_notices=args.mav_notices, mav_paid_rate=args.mav_paid_rate, scenarios=args.scenario or ["baseline", "sdd-lifecycle", "mav-lifecycle", "remittance-noise"])
    scen = [load_scenario(s) for s in cfg.scenarios]
    world = generate_world(cfg, scen)
    out_dir = Path(args.out) / episode
    written: list[str] = []
    for fid in [f.strip() for f in args.format.split(",") if f.strip()]:
        cls = REGISTRY[fid]
        sink = cls()
        if "A-02" in cls.assumptions:
            if not args.allow_assumed_layouts:
                print(json.dumps({"format": fid, "skipped": "assumed layout (A-02); pass --allow-assumed-layouts"}))
                continue
            sink.allow_assumed_layouts = True
        written += [str(p) for p in sink.emit(world.view(), Selection(), out_dir)]
    ak = write_answer_key(world, generator_block(cfg, [s.scenario_id for s in scen]), args.episodes_dir)
    print(json.dumps({"episode": episode, "accounts": len(world.accounts), "movements": len(world.movements), "collections": len(world.collections),
                      "mav_notices": len(world.mav_notices), "files": written, "answer_key": str(ak)}, indent=2))


if __name__ == "__main__":
    main()
