"""OEISHeadroom CLI.

  oeisheadroom survey [--limit N] [--out FILE]
      Filter all 399,277 OEIS sequences for ones with computational headroom
      left: counting problems that stopped early because a brute force ran out
      of patience rather than because the problem is hard. Downloads the bulk
      dumps once (~40 MB) and caches them.

  oeisheadroom verify [--live]
      THE GATE. For each attacked sequence, check the implementation reproduces
      every term OEIS already publishes, then report what lies past them. Exits
      non-zero if any sequence fails. --live re-fetches from OEIS instead of
      trusting the committed snapshot.

  oeisheadroom snapshot
      Re-record what OEIS publishes today into published.json, so that `verify`
      is reproducible offline and in CI.

  oeisheadroom show SEQ
      Print one sequence's published terms and everything computed past them.

An extension here is never asserted, only demonstrated: `verify` reproduces the
published terms from scratch and you can watch it do it. Nothing in this
repository has been submitted to the OEIS.
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
    from .verify import check_all, fetch_published

    if not os.path.isdir(SEQ_DIR) or not _seq_files():
        print("no sequence implementations found in sequences/", file=sys.stderr)
        return 1

    results = check_all(SEQ_DIR, SNAPSHOT)

    if args.live:
        print("re-checking the snapshot against OEIS...\n")
        drift = 0
        with open(SNAPSHOT, encoding="utf-8") as fh:
            snap = json.load(fh)["sequences"]
        for sid, rec in sorted(snap.items()):
            live = fetch_published(sid)
            if live is None:
                print(f"  {sid}  UNREACHABLE - could not confirm against OEIS")
                drift += 1
            elif live != rec["data"]:
                print(f"  {sid}  DRIFT - OEIS now publishes {len(live)} terms, "
                      f"snapshot has {len(rec['data'])}")
                drift += 1
            else:
                print(f"  {sid}  matches OEIS ({len(live)} terms)")
        print()
        if drift:
            print(f"{drift} sequence(s) could not be confirmed current.\n")

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
    if total_new == 0:
        print("  no sequence was extended. The implementations are correct and "
              "add nothing, which is a result, not a pass.")
    return 0


def cmd_snapshot(args) -> int:
    from .verify import snapshot
    doc = snapshot(SEQ_DIR, SNAPSHOT)
    n = len(doc["sequences"])
    print(f"snapshotted {n} sequence(s) at {doc['fetched_utc']}")
    for sid, rec in sorted(doc["sequences"].items()):
        print(f"  {sid}  {rec['n_terms']} published terms")
    if doc.get("failed"):
        print(f"  COULD NOT FETCH: {', '.join(doc['failed'])}")
        return 1
    return 0


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
                   help="re-fetch from OEIS instead of trusting the snapshot")
    v.set_defaults(func=cmd_verify)

    sub.add_parser("snapshot", help="re-record what OEIS publishes today"
                   ).set_defaults(func=cmd_snapshot)

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
