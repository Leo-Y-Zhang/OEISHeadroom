"""OEISHeadroom CLI.

  oeisheadroom survey [--limit N] [--out FILE]
      Filter all 399,277 OEIS sequences for ones with computational headroom
      left: counting problems that stopped early because a brute force ran out
      of patience rather than because the problem is hard. Downloads the bulk
      dumps once (~40 MB) and caches them.

  oeisheadroom verify [--live]
      THE GATE. For each attacked sequence, check the implementation reproduces
      every term OEIS already publishes, then report what lies past them. Exits
      non-zero if any sequence fails. --live additionally fetches what the OEIS
      publishes today (the b-file, and the DATA field where the b-file was
      uploaded rather than synthesized from it) and confirms it matches the
      frozen baseline plus the terms just computed -- a check on the published
      record, not on this repository.

  oeisheadroom bfile [--outdir DIR] [--check]
      Render an OEIS b-file ("n a(n)" per line) for every sequence that passes
      the gate, and say which extensions are too long for the DATA field and
      therefore need one. Refuses to write a b-file for a sequence that fails.

  oeisheadroom snapshot [--out FILE] [--force]
      Re-record what OEIS publishes today. published.json is the FROZEN
      pre-submission baseline and overwriting it needs --force: this
      repository's terms are in the OEIS now, so a re-fetch would fold its own
      output into the data it is checked against.

  oeisheadroom show SEQ
      Print one sequence's published terms and everything computed past them.

An extension here is never asserted, only demonstrated: `verify` reproduces the
published terms from scratch and you can watch it do it. All seven extensions
have since been submitted by the author and accepted by the OEIS editors;
`verify --live` is what checks that what they published is what was computed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEQ_DIR = os.path.join(ROOT, "sequences")
SNAPSHOT = os.path.join(ROOT, "published.json")
CACHE = os.path.join(ROOT, ".oeis-cache")
SURVEY_OUT = os.path.join(ROOT, "survey.json")
BFILE_DIR = os.path.join(ROOT, "bfiles")


def cmd_survey(args) -> int:
    from .survey import survey, write
    print("downloading OEIS bulk dumps (cached after the first run)...")
    rows = survey(CACHE)
    write(rows, args.out or SURVEY_OUT)
    print(f"\n{len(rows):,} sequences have headroom by these criteria\n")
    print(f"  {'id':<9} {'terms':>5} {'last':>13} {'growth':>7}  name")
    print(f"  {'-' * 9} {'-' * 5} {'-' * 13} {'-' * 7}  {'-' * 46}")
    for r in rows[:args.limit]:
        print(f"  {r['id']:<9} {r['n_terms']:>5} {r['last']:>13,} "
              f"{r['growth']:>7}  {r['name'][:46]}")
    print(f"\nwritten to {args.out or SURVEY_OUT}")
    return 0


def cmd_verify(args) -> int:
    from .verify import check_all

    if not os.path.isdir(SEQ_DIR) or not _seq_files():
        print("no sequence implementations found in sequences/", file=sys.stderr)
        return 1

    results = check_all(SEQ_DIR, SNAPSHOT)

    live_failed = False
    if args.live:
        from .verify import confirm_live

        print("confirming the published record against the frozen baseline "
              "plus what was just computed...\n")
        with open(SNAPSHOT, encoding="utf-8") as fh:
            snap_doc = json.load(fh)
        live = confirm_live(results, snap_doc["sequences"])
        if not live:
            print("  nothing to confirm: no sequence passed the gate\n")
        else:
            w = max(len(x.seq_id) for x in live)
            for x in live:
                print(f"  {x.seq_id:<{w}}  {x.status:<11} {x.detail}")
            confirmed = sum(x.n_confirmed for x in live)
            bad = [x for x in live if not x.ok]
            print()
            print(f"  baseline frozen at {snap_doc['fetched_utc'][:10]}; "
                  f"{confirmed} term(s) computed here are published in OEIS and agree")
            if bad:
                # Not a warning. A MISMATCH means a wrong value is in the OEIS
                # under the author's name, or is in this repository; either way
                # something has to be corrected by a human, and a green run
                # would bury it.
                print(f"  {len(bad)} sequence(s) NOT confirmed: "
                      + ", ".join(f"{x.seq_id} {x.status}" for x in bad))
                live_failed = True
            print()

    width = max(len(r.seq_id) for r in results)
    print(f"  {'sequence':<{width}}  {'pub':>4} {'new':>4}  {'time':>7}  verdict")
    print(f"  {'-' * width}  {'-' * 4} {'-' * 4}  {'-' * 7}  {'-' * 44}")
    for r in results:
        mark = "ok  " if r.ok else "FAIL"
        print(f"  {r.seq_id:<{width}}  {r.n_published:>4} {r.n_new:>4}  "
              f"{r.seconds:>6.1f}s  {mark} {r.reason}")

    passed = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    total_new = sum(r.n_new for r in passed)
    print()
    print(f"  {len(passed)}/{len(results)} sequences reproduce every published "
          f"term; {total_new} new terms computed past them")
    if failed:
        print(f"  {len(failed)} FAILED - nothing from those is a claim")
        return 1
    if live_failed:
        return 1
    if total_new == 0:
        print("  no sequence was extended. The implementations are correct and "
              "add nothing, which is a result, not a pass.")
    return 0


def cmd_snapshot(args) -> int:
    from .verify import snapshot

    out = args.out or SNAPSHOT
    # The baseline is load-bearing, and overwriting it does not look like
    # damage: the gate would go on printing 7/7, only now against data this
    # repository partly supplied. So the destructive default is off. The
    # refusal comes before the fetch, so a mistyped command costs nothing and
    # touches neither the file nor oeis.org.
    if out == SNAPSHOT and os.path.exists(SNAPSHOT) and not args.force:
        with open(SNAPSHOT, encoding="utf-8") as fh:
            when = json.load(fh).get("fetched_utc", "?")[:10]
        print(f"refusing to overwrite the frozen baseline (published.json, "
              f"fetched {when}).\n"
              f"This repository's terms are published in the OEIS now, so "
              f"re-fetching would fold\nits own output into the data it is "
              f"checked against, and the gate would be grading\nits own "
              f"homework while still printing a pass.\n\n"
              f"  oeisheadroom verify --live      confirm the live data instead "
              f"(what you probably want)\n"
              f"  oeisheadroom snapshot --out F   write today's data somewhere "
              f"else and diff it\n"
              f"  oeisheadroom snapshot --force   overwrite anyway, and re-read "
              f"the gate's premise first",
              file=sys.stderr)
        return 2
    doc = snapshot(SEQ_DIR, out)
    n = len(doc["sequences"])
    print(f"snapshotted {n} sequence(s) at {doc['fetched_utc']} -> {out}")
    for sid, rec in sorted(doc["sequences"].items()):
        print(f"  {sid}  {rec['n_terms']} published terms")
    if doc.get("failed"):
        print(f"  COULD NOT FETCH: {', '.join(doc['failed'])}")
        return 1
    return 0


def cmd_bfile(args) -> int:
    """Render b-files from verified output, and say which entries need one."""
    from .verify import DATA_CAP, bfile_text, check_all, data_line, fits_in_data

    results = check_all(SEQ_DIR, SNAPSHOT)
    with open(SNAPSHOT, encoding="utf-8") as fh:
        snap = json.load(fh)["sequences"]

    outdir = args.outdir or BFILE_DIR
    if not args.check:
        os.makedirs(outdir, exist_ok=True)

    rc = 0
    rows = []
    for r in results:
        if not r.ok:
            # Default-deny, same as the gate: a b-file is a claim in a format
            # that is easy to upload and hard to retract.
            print(f"  {r.seq_id}  REFUSED - {r.reason}", file=sys.stderr)
            rc = 1
            continue
        full = list(snap.get(r.seq_id, {}).get("data") or []) + list(r.new_terms)
        text = bfile_text(r.seq_id, r.offset, full)
        path = os.path.join(outdir, f"b{r.seq_id[1:]}.txt")
        if args.check:
            have = None
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    have = fh.read()
            if have != text:
                print(f"  {r.seq_id}  STALE - {path} does not match the verified "
                      f"terms", file=sys.stderr)
                rc = 1
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        rows.append((r.seq_id, r.offset, full, path))

    if rows:
        width = max(len(x[0]) for x in rows)
        print(f"  {'sequence':<{width}}  {'terms':>5} {'DATA':>5}  b-file")
        print(f"  {'-' * width}  {'-' * 5} {'-' * 5}  {'-' * 46}")
        for sid, offset, full, _path in rows:
            chars = len(data_line(full))
            need = "REQUIRED" if not fits_in_data(full) else "optional"
            print(f"  {sid:<{width}}  {len(full):>5} {chars:>5}  {need:<8} "
                  f"a({offset})..a({offset + len(full) - 1})")
        over = [x for x in rows if not fits_in_data(x[2])]
        print()
        print(f"  DATA holds about {DATA_CAP} characters; {len(over)} of "
              f"{len(rows)} extension(s) do not fit and need a b-file"
              + (f": {', '.join(x[0] for x in over)}" if over else ""))
        if args.check:
            print(f"  checked against {outdir}")
        else:
            print(f"  written to {outdir}")
    return rc


def cmd_show(args) -> int:
    from .verify import check_one
    sid = args.seq.upper()
    path = os.path.join(SEQ_DIR, f"{sid.lower()}.py")
    if not os.path.exists(path):
        print(f"no implementation for {sid}", file=sys.stderr)
        return 2
    with open(SNAPSHOT, encoding="utf-8") as fh:
        snap = json.load(fh)["sequences"]
    r = check_one(path, snap)
    print(f"{sid}  {'VERIFIED' if r.ok else 'FAILED'} - {r.reason}")
    print(f"  published : {r.n_published} terms")
    if r.new_terms:
        print(f"  new       : {r.n_new} terms")
        print(f"  {', '.join(str(t) for t in r.new_terms)}")
    return 0 if r.ok else 1


def _seq_files() -> list[str]:
    if not os.path.isdir(SEQ_DIR):
        return []
    return [f for f in os.listdir(SEQ_DIR)
            if f.startswith("a") and f.endswith(".py")]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="oeisheadroom", description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("survey", help="find sequences with headroom left")
    s.add_argument("--limit", type=int, default=40)
    s.add_argument("--out")
    s.set_defaults(func=cmd_survey)

    v = sub.add_parser("verify", help="the gate: reproduce every published term")
    v.add_argument("--live", action="store_true",
                   help="also confirm the OEIS publishes the verified terms "
                        "(DATA field and b-file); the gate itself still runs "
                        "against the frozen snapshot")
    v.set_defaults(func=cmd_verify)

    b = sub.add_parser("bfile", help="render OEIS b-files from verified terms")
    b.add_argument("--outdir", help="where to write (default: bfiles/)")
    b.add_argument("--check", action="store_true",
                   help="do not write; fail if existing b-files are stale")
    b.set_defaults(func=cmd_bfile)

    n = sub.add_parser("snapshot", help="re-record what OEIS publishes today")
    n.add_argument("--out", help="write here instead of published.json")
    n.add_argument("--force", action="store_true",
                   help="overwrite the frozen baseline (read the gate's premise first)")
    n.set_defaults(func=cmd_snapshot)

    w = sub.add_parser("show", help="one sequence, published and new")
    w.add_argument("seq")
    w.set_defaults(func=cmd_show)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
