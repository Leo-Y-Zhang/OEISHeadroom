"""Find OEIS sequences with computational headroom left in them.

The OEIS marks sequences whose author wants more terms with the keyword `more`.
There are 26,751 of them. Almost all are unattackable: probable-prime searches
owned by specialists with optimised software, or famous problems that have had
supercomputers pointed at them for decades. This module finds the residue -
sequences that stopped early because somebody's brute force ran out of patience,
not because the problem is hard.

Two things had to be got right, and both were got wrong first.

**The search API cannot do this.** It caps pagination at start=200, so it will
not enumerate a 19,113-result query however politely you ask. The bulk dumps
(names.gz, stripped.gz) carry all 399,277 sequences and can be filtered offline
with complete coverage and no rate limit.

**Few terms means HARD, not neglected - unless the terms are also small.** A
first pass keyed on term count alone and returned Dedekind numbers, posets and
polycubes: every one famous, every one hopeless. Those sequences are short
because the answers explode. The signal that actually separates neglect from
difficulty is the magnitude of the last published term. A counting sequence that
stops after twelve terms at a value of forty thousand did not stop because the
answer got big.

**And that inference only holds if the sequence grows.** Counts of maximum-size
objects oscillate violently - A375299, longest winning paths in n X n Hex, runs
`... 1298, 83648, 16631833, 70630` - so for those the last term measures nothing
at all. Checked against the authoritative %S/%T lines: the data is real, the
assumption was wrong. Monotonicity is therefore a filter criterion, not a
cosmetic preference.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import subprocess

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")

BULK = {"names": "https://oeis.org/names.gz",
        "stripped": "https://oeis.org/stripped.gz"}

# Language marking a counting problem with a finite, checkable answer.
ENUMERATIVE = re.compile(r"\bnumber of\b|\bnumber\s+of\s+ways\b|\benumerat", re.I)

# Structures where a transfer matrix, a DP over a boundary, or canonical
# generation is the standard weapon and brute force is what usually got
# published.
STRUCTURE = re.compile(
    r"\bpolyomino|\btiling|\blattice\b|\bwalks?\b|\bpaths?\b|\bgraphs?\b|"
    r"\btrees?\b|\bposets?\b|\bmatri(?:x|ces)\b|\bpermutations?\b|"
    r"\bpartitions?\b|\bnecklaces?\b|\bpolygons?\b|\bgrid\b|\btableaux\b|"
    r"\bself-avoiding\b|\bhypergraph|\bset\s+partitions?\b|\bcompositions?\b|"
    r"\bcolou?rings?\b|\bcircuits?\b|\bcodes?\b|\barrangements?\b", re.I)

# No edge here: prime hunting is a specialist sport, digit chases depend on a
# base rather than a structure, and a triangle read by rows is a 2D array whose
# "terms" are not what this filter thinks they are.
EXCLUDE = re.compile(
    r"\bprime|\bprp\b|\brepunit|\bsemiprime|\bfactor(?:isation|ization)\b|"
    r"\bdecimal expansion\b|\bcontinued fraction\b|\bdigits? of\b|\bMersenne\b|"
    r"\bpseudoprime|\bcomposite\b|\bdivisor|\bbase \d+\b|\bin base\b|"
    r"\bconstant\b|\bTriangle read\b|\bread by (?:rows|antidiagonals)\b|"
    r"\bIrregular triangle\b|\bsquare array\b|\bA\d{6}\b", re.I)

MIN_TERMS, MAX_TERMS = 8, 25
MIN_LAST, MAX_LAST = 1_000, 10 ** 13
MAX_GROWTH = 12.0


def download(cache_dir: str) -> dict[str, str]:
    """Fetch the OEIS bulk dumps, once. Roughly 40 MB the first time."""
    os.makedirs(cache_dir, exist_ok=True)
    paths = {}
    for name, url in BULK.items():
        path = os.path.join(cache_dir, f"{name}.gz")
        if not os.path.exists(path) or os.path.getsize(path) < 1_000_000:
            # Download beside the cache and move into place only once curl has
            # finished. A dump over the size floor is trusted on sight, so one
            # cut short by the timeout, a dropped connection or Ctrl-C would
            # sit in the cache and fail every later run inside gzip. And -f, so
            # an HTTP error is a failed download rather than an error page
            # saved under the dump's name.
            part = path + ".part"
            try:
                subprocess.run(["curl", "-sfL", "-A", UA, url, "-o", part],
                               check=True, timeout=900)
                os.replace(part, path)
            finally:
                if os.path.exists(part):
                    os.remove(part)
        paths[name] = path
    return paths


def load(cache_dir: str) -> dict[str, dict]:
    paths = download(cache_dir)
    seqs: dict[str, dict] = {}
    # errors="replace" is deliberate: a handful of names carry non-UTF-8 bytes,
    # and a name that renders imperfectly is not a reason to drop a sequence.
    with gzip.open(paths["names"], "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("A"):
                aid, _, name = line.rstrip("\n").partition(" ")
                seqs[aid] = {"id": aid, "name": name}
    with gzip.open(paths["stripped"], "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("A"):
                aid, _, data = line.rstrip("\n").partition(" ")
                if aid in seqs:
                    seqs[aid]["data"] = data.strip().strip(",")
    return seqs


def assess(name: str, data: str) -> dict | None:
    """Return a candidate record, or None with no explanation.

    `survey` reports only the sequences that pass, not how many fell out at
    each stage. To see why a particular sequence was dropped, call this on its
    name and data directly.
    """
    if not data or EXCLUDE.search(name):
        return None
    if not (ENUMERATIVE.search(name) and STRUCTURE.search(name)):
        return None
    try:
        terms = [int(x) for x in data.split(",") if x.strip()]
    except ValueError:
        return None
    if not (MIN_TERMS <= len(terms) <= MAX_TERMS):
        return None

    # Growth must be genuine, or "last term is small" means nothing. Ignore the
    # first third: many counting sequences are flat or erratic at tiny n and
    # only settle once the structure has room to exist.
    tail = terms[len(terms) // 3:]
    if any(b <= a for a, b in zip(tail, tail[1:], strict=False)):
        return None
    last = terms[-1]
    if last != max(terms) or not (MIN_LAST <= last < MAX_LAST):
        return None
    ratios = [b / a for a, b in zip(tail, tail[1:], strict=False) if a > 0]
    growth = max(ratios) if ratios else 0.0
    if growth > MAX_GROWTH:
        return None
    return {"n_terms": len(terms), "last": last, "growth": round(growth, 2)}


def survey(cache_dir: str) -> list[dict]:
    seqs = load(cache_dir)
    out = []
    for aid, rec in seqs.items():
        verdict = assess(rec["name"], rec.get("data") or "")
        if verdict:
            out.append({"id": aid, "name": rec["name"],
                        "data": rec["data"], **verdict})
    # Headroom ranking: many published terms to validate an implementation
    # against, a small final value, and gentle growth all point the same way.
    out.sort(key=lambda k: (k["last"] / max(k["n_terms"], 1), k["growth"]))
    return out


def write(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rows, fh, indent=1)
        fh.write("\n")
