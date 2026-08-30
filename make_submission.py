"""Generate SUBMISSION.md: copy-paste-ready OEIS edits, and nothing more.

This produces exactly what a human needs to paste into an OEIS draft, in the
shape the OEIS wants: a DATA line, a line to APPEND to EXTENSIONS, and a short
note for the submission box. No b-file, no comment field.

The DATA line is truncated to the OEIS's own limit rather than dumping every
computed term, and the script reports how many were held back. A DATA line that
overflows gets silently mangled by the submission form, which would look like a
typo by the submitter rather than a tool that did not check.

The EXTENSIONS field ACCUMULATES. It is generated here as an addition to
whatever the sequence already carries, because editing that field in place is
how credit for someone else's earlier terms gets deleted -- an editor has
already bounced one of this author's drafts for exactly that. A337114 currently
credits Bert Dobbelaere for a(13)-a(24); that line is reproduced here so it is
obvious it must survive.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from oeisheadroom.verify import check_all  # noqa: E402

SEQ_DIR = os.path.join(ROOT, "sequences")
SNAPSHOT = os.path.join(ROOT, "published.json")
SURVEY = os.path.join(ROOT, "survey.json")
OE_DIR = sys.argv[1] if len(sys.argv) > 1 else None

# The OEIS DATA line (%S/%T/%U together) is limited to about 260 characters.
# Staying under it is the difference between a clean draft and a mangled one.
DATA_LIMIT = 260
REPO = "https://github.com/Leo-Y-Zhang/OEISHeadroom"
CREDIT = "Leo Y. Zhang"
DATE = "Aug 30 2026"


EXT_SNAPSHOT = os.path.join(ROOT, "extensions.json")


def existing_ext(seq_id: str) -> list[str]:
    """What EXTENSIONS the sequence already carries.

    Read from the committed snapshot by default. Reporting "none" when the
    truth is unknown would be the worst possible failure here: it is the exact
    prompt to retype the field and delete somebody else's credit. So a missing
    snapshot raises rather than returning an empty list.
    """
    if OE_DIR:
        path = os.path.join(OE_DIR, f"{seq_id}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            rec = doc["results"][0] if isinstance(doc, dict) else doc[0]
            return list(rec.get("ext") or [])
    if not os.path.exists(EXT_SNAPSHOT):
        raise SystemExit(
            "extensions.json is missing. Refusing to generate a submission "
            "pack that would claim every sequence has no prior EXTENSIONS "
            "line -- that is how existing credit gets deleted.")
    with open(EXT_SNAPSHOT, encoding="utf-8") as fh:
        doc = json.load(fh)
    if seq_id not in doc["sequences"]:
        raise SystemExit(f"{seq_id} is not in extensions.json; re-fetch it "
                         f"before generating a pack that touches it.")
    return list(doc["sequences"][seq_id]["ext"])


def fit(terms: list[int]) -> tuple[list[int], int]:
    """Longest prefix whose comma-joined form fits the OEIS DATA limit."""
    keep: list[int] = []
    for t in terms:
        trial = keep + [t]
        if len(",".join(str(x) for x in trial)) > DATA_LIMIT:
            break
        keep = trial
    return keep, len(terms) - len(keep)


def main() -> int:
    names = {}
    if os.path.exists(SURVEY):
        with open(SURVEY, encoding="utf-8") as fh:
            names = {r["id"]: r["name"] for r in json.load(fh)}

    results = [r for r in check_all(SEQ_DIR, SNAPSHOT) if r.ok and r.n_new]
    results.sort(key=lambda r: r.seq_id)

    out = [HEADER.format(n=len(results),
                         total=sum(r.n_new for r in results),
                         repo=REPO)]

    for r in results:
        mod = os.path.join(SEQ_DIR, f"{r.seq_id.lower()}.py")
        ns: dict = {}
        with open(mod, encoding="utf-8") as fh:
            exec(compile(fh.read(), mod, "exec"), ns)   # noqa: S102
        offset = int(ns["OFFSET"])
        published = list(ns["PUBLISHED"])
        full = published + r.new_terms

        keep, dropped = fit(full)
        n_new_kept = len(keep) - len(published)
        first_new = offset + len(published)
        last_kept = offset + len(keep) - 1

        prior = existing_ext(r.seq_id)
        ext_line = (f"a({first_new})-a({last_kept}) from {CREDIT}, {DATE}")

        note = NOTE.format(npub=len(published), first=first_new, last=last_kept)
        words = len(note.split())

        out.append(SECTION.format(
            sid=r.seq_id,
            name=names.get(r.seq_id, ""),
            offset=offset,
            npub=len(published),
            nnew=n_new_kept,
            nheld=dropped,
            total=len(keep),
            data=",".join(str(x) for x in keep),
            datachars=len(",".join(str(x) for x in keep)),
            prior=("\n".join(f"    %E {e}" for e in prior)
                   if prior else "    (none - this sequence has no EXTENSIONS "
                                 "field yet, so your line is the first)"),
            prior_warn=(PRIOR_WARN.format(prior=prior[0]) if prior else ""),
            ext=ext_line,
            note=note,
            words=words,
            held=(HELD.format(n=dropped, idx=last_kept + 1)
                  if dropped else "All computed terms fit the DATA line."),
        ))

    out.append(FOOTER)
    text = "\n".join(out)
    bad = sorted({c for c in text if ord(c) > 127})
    if bad:
        print(f"ERROR: non-ASCII in output: {bad}", file=sys.stderr)
        return 1
    with open(os.path.join(ROOT, "SUBMISSION.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"SUBMISSION.md written: {len(results)} sequences")
    return 0


HEADER = """# OEIS submission pack

Everything needed to submit {n} extensions, in the order the OEIS form asks for
it. **Nothing here has been submitted.** Each block is copy-paste ready.

Generated from the verifier's real output by `make_submission.py`, so the terms
below are the ones `oeisheadroom verify` recomputes. If you change anything in
`sequences/`, regenerate this file rather than editing it.

## Before you paste anything

1. **Check it yourself.** `pip install -e . && oeisheadroom verify` reproduces
   all published terms and recomputes every new one in about a minute. If that
   does not come back clean, do not submit.
2. **Sign in at oeis.org, open the sequence, click "edit".** One sequence per
   draft. There is no hurry and no deadline.
3. **Edit only the two fields given below, plus the note.** No b-file. No new
   comment field. Smaller drafts get approved faster and argue less.
4. **The EXTENSIONS field ACCUMULATES.** Add your line *underneath* whatever is
   already there. Never retype or replace the existing lines -- that deletes
   someone else's credit, and it is what an editor bounced a previous draft of
   yours for.
5. **Write any reply to an editor in your own words.** That is the OEIS's
   policy and it is not negotiable. Do not paste anything generated here into a
   conversation with an editor.

Total across all {n} sequences: **{total} new terms**, each one recomputed by a
program that first reproduces every already-published value exactly.

Repository, if an editor asks where the terms came from: {repo}

---
"""

SECTION = """
## {sid}

> {name}

Offset {offset}. Currently {npub} published terms; this adds **{nnew}**, taking
the DATA line to {total} terms ({datachars} chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
{data}
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
{prior}
```
{prior_warn}
Add this as a NEW line, keeping anything above it:

```
{ext}
```

**3. Note for the submission box** ({words} words):

```
{note}
```

{held}

---
"""

PRIOR_WARN = """
> **Keep that line.** `{prior}` must still be there when you save. Retyping the
> EXTENSIONS field instead of appending to it is exactly the edit that got a
> previous draft of yours reverted.
"""

# The submission box is a private note to the editors, not a public field, so
# the URL belongs inside it rather than as a %H link. That keeps the draft to
# two edited fields, which is the whole point of submitting a small draft.
NOTE = ("Extended by an independent Python reimplementation that first "
        "reproduces all {npub} published terms exactly. Verification and code: "
        "github.com/Leo-Y-Zhang/OEISHeadroom")

HELD = ("**{n} further computed terms are not included**, because the DATA line "
        "would exceed the OEIS length limit from a({idx}) onward. They are in "
        "the repository. Submitting them would need a b-file, which is a "
        "separate and larger conversation with an editor -- not worth opening "
        "on a first draft.")

FOOTER = """
## If an editor replies

Answer in your own words. The useful facts, in case you need them:

- The terms come from an independent reimplementation, not from the existing
  Mathematica program in the entry. The existing programs are brute force --
  for example A353403's takes every subset of every composition -- which is why
  these sequences stopped where they did.
- Correctness evidence is that each program reproduces **every** already-
  published term exactly before computing anything new. Several were also
  checked against a second, independently written brute force.
- Anyone can re-run the check: the repository's `verify` command recomputes the
  published terms and the new ones from scratch, and its CI does the same on
  every push.

**Do not chase a draft.** Sitting in `proposed` is normal and an editor will get
to it. If one asks for a change, make that change; if one reverts something,
read what they actually said before re-editing.
"""

if __name__ == "__main__":
    raise SystemExit(main())
