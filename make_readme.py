"""Render README.md from a template plus the verifier's actual output.

Every number in the README is produced by running the gate, not typed. A README
with hand-copied results drifts from the code the moment either changes, and the
drift is invisible: the document still reads as though it were checked. So this
refuses to write a file with an unfilled placeholder left in it, which makes a
stale README a build failure rather than a quiet lie.

Run it after `oeisheadroom verify`, or just run it -- it verifies for itself.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from oeisheadroom.verify import check_all  # noqa: E402

SEQ_DIR = os.path.join(ROOT, "sequences")
SNAPSHOT = os.path.join(ROOT, "published.json")
SURVEY = os.path.join(ROOT, "survey.json")
TEMPLATE = os.path.join(ROOT, "README.template.md")
OUT = os.path.join(ROOT, "README.md")


def load_names() -> dict[str, str]:
    if not os.path.exists(SURVEY):
        return {}
    with open(SURVEY, encoding="utf-8") as fh:
        return {r["id"]: r["name"] for r in json.load(fh)}


def results_table(results, names) -> str:
    rows = ["| sequence | published | new | total | what it counts |",
            "|---|---:|---:|---:|---|"]
    for r in sorted(results, key=lambda x: -x.n_new):
        name = names.get(r.seq_id, "")
        name = (name[:74] + "...") if len(name) > 77 else name
        if r.ok:
            new = f"**+{r.n_new}**" if r.n_new else "0"
            rows.append(f"| [{r.seq_id}](https://oeis.org/{r.seq_id}) "
                        f"| {r.n_published} | {new} | {r.n_published + r.n_new} "
                        f"| {name} |")
        else:
            rows.append(f"| [{r.seq_id}](https://oeis.org/{r.seq_id}) "
                        f"| {r.n_published} | FAILED | - | {r.reason} |")
    return "\n".join(rows)


def terms_block(results) -> str:
    out = []
    for r in sorted(results, key=lambda x: x.seq_id):
        if not (r.ok and r.new_terms):
            continue
        mod = os.path.join(SEQ_DIR, f"{r.seq_id.lower()}.py")
        offset = 0
        with open(mod, encoding="utf-8") as fh:
            m = re.search(r"^OFFSET\s*=\s*(\d+)", fh.read(), re.M)
            if m:
                offset = int(m.group(1))
        first = offset + r.n_published
        last = first + r.n_new - 1
        out.append(f"**{r.seq_id}** -- a({first})..a({last}):\n\n```\n"
                   + ", ".join(str(t) for t in r.new_terms) + "\n```\n")
    return "\n".join(out) if out else "_No sequence was extended._\n"


def main() -> int:
    with open(SNAPSHOT, encoding="utf-8") as fh:
        snap_doc = json.load(fh)
    results = check_all(SEQ_DIR, SNAPSHOT)
    names = load_names()

    passed = [r for r in results if r.ok]
    extended = [r for r in passed if r.n_new]
    n_survey = 0
    if os.path.exists(SURVEY):
        with open(SURVEY, encoding="utf-8") as fh:
            n_survey = len(json.load(fh))

    fields = {
        "RESULTS_TABLE": results_table(results, names),
        "NEW_TERMS": terms_block(results),
        "N_ATTACKED": str(len(results)),
        "N_VERIFIED": str(len(passed)),
        "N_EXTENDED": str(len(extended)),
        "N_NEW_TERMS": str(sum(r.n_new for r in passed)),
        "N_PUBLISHED_CHECKED": str(sum(r.n_published for r in passed)),
        "N_SURVEY": f"{n_survey:,}",
        "SNAPSHOT_DATE": snap_doc["fetched_utc"][:10],
    }

    with open(TEMPLATE, encoding="utf-8") as fh:
        text = fh.read()
    for key, val in fields.items():
        text = text.replace("{{" + key + "}}", val)

    left = re.findall(r"\{\{([A-Z_]+)\}\}", text)
    if left:
        print(f"ERROR: unfilled placeholders: {sorted(set(left))}", file=sys.stderr)
        return 1

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    non_ascii = sorted({c for c in text if ord(c) > 127})
    if non_ascii:
        print(f"ERROR: README is not ASCII: {non_ascii}", file=sys.stderr)
        return 1
    print(f"README.md written: {len(passed)}/{len(results)} verified, "
          f"{fields['N_NEW_TERMS']} new terms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
