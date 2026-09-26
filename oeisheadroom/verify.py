"""The gate. Nothing in this repository is a claim until this passes.

An extension to an OEIS sequence is worth exactly nothing unless the program
that produced it also reproduces every term the OEIS already publishes. That is
the whole argument: agreeing with twenty-five published values by luck is not
possible, so exact agreement is proof that the definition was understood, and
disagreement on even one value proves it was not.

So the check runs in this order and refuses to skip a step:

  1. The module's PUBLISHED list must match the snapshot taken from OEIS. This
     catches a module that quietly edited the published data to fit its output.
  2. The module must recompute those published terms exactly. This catches a
     wrong implementation.
  3. Only then is anything past the published data reported as an extension.

Two design decisions worth defending. Verification is DEFAULT-DENY: a module
that fails to import, or whose terms() raises, or that has no snapshot, is a
FAILURE and never a skip - an unrunnable check and a passing check must not look
alike. And the published data is snapshotted to a file with the date it was
fetched, so `verify` works offline and in CI. A verifier that silently needs the
network is a verifier that silently stops running.

That snapshot is now FROZEN, and the freeze is the whole argument rather than
housekeeping. All seven extensions have since been accepted by the OEIS, so what
oeis.org publishes today already contains this repository's own output. Re-fetch
it into the baseline and step 2 above stops being a test: the program would be
recomputing numbers it supplied, and agreeing with itself is worth nothing. The
baseline stays at the pre-submission data -- 153 terms this repository had no
hand in -- and `snapshot` refuses to overwrite it without --force.

What the live data is good for is a different check, and one that could not run
until the terms were accepted: `verify --live` confirms OEIS now publishes
exactly the terms computed here. Disagreement there is not drift to note, it is
a wrong value sitting in the OEIS under the author's name, or a wrong value
here. See confirm_one for the four ways that can go.
"""
from __future__ import annotations

import dataclasses
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")


@dataclasses.dataclass
class Result:
    seq_id: str
    ok: bool
    reason: str
    n_published: int = 0
    n_computed: int = 0
    new_terms: list[int] = dataclasses.field(default_factory=list)
    seconds: float = 0.0
    offset: int = 0

    @property
    def n_new(self) -> int:
        return len(self.new_terms)


def _fetch_failed(url: str, why: str) -> None:
    """Say why a fetch failed. The verdict is UNREACHABLE either way, but that
    alone does not say whether to retry, change the client or ask the OEIS, so
    the reason goes to stderr, which is where a CI log will show it."""
    print(f"  fetch failed: {url}: {why}", file=sys.stderr)


def _get(url: str, timeout: int) -> bytes | None:
    """GET a URL with curl, following redirects. None on any failure, an HTTP
    error status included."""
    try:
        out = subprocess.run(["curl", "-s", "-S", "-f", "-L", "-A", UA, url],
                             capture_output=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError) as exc:
        _fetch_failed(url, repr(exc))
        return None
    if out.returncode != 0:
        _fetch_failed(url, out.stderr.decode("utf-8", "replace").strip()
                      or f"curl exited {out.returncode}")
        return None
    return out.stdout


def fetch_published(seq_id: str, timeout: int = 60) -> list[int] | None:
    """Pull a sequence's DATA line straight from OEIS. None on any failure.

    Note the explicit utf-8 decode: OEIS records carry accented author names,
    and Windows' cp1252 default raises UnicodeDecodeError on them.
    """
    url = f"https://oeis.org/search?q=id:{seq_id}&fmt=json"
    body = _get(url, timeout)
    if body is None:
        return None
    try:
        doc = json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        _fetch_failed(url, f"the response is not JSON: {body[:80]!r}")
        return None
    # The search answers with a bare list of records, or null for no hit; the
    # older API wrapped the same list as {"results": [...]}, with null for no
    # hit. Anything else is a failure to fetch, not an exception: one entry
    # that will not answer must not take every other verdict down with it.
    recs = doc.get("results") if isinstance(doc, dict) else doc
    if not isinstance(recs, list) or not recs or not isinstance(recs[0], dict):
        _fetch_failed(url, f"no record in the response: {body[:80]!r}")
        return None
    data = recs[0].get("data")
    if not isinstance(data, str):
        return None
    try:
        return [int(x) for x in data.split(",") if x.strip()]
    except ValueError:
        return None


def fetch_bfile(seq_id: str, timeout: int = 60) -> str | None:
    """The b-file the OEIS serves for a sequence, as text. None on any failure.

    This is where an extension too long for the DATA field is published, so it
    is the only place the end of one can be checked.
    """
    body = _get(f"https://oeis.org/{seq_id}/b{seq_id[1:]}.txt", timeout)
    return None if body is None else body.decode("utf-8-sig", "replace")


class _FromSource(importlib.machinery.SourceFileLoader):
    """Compile a module from its file as it is now, never from __pycache__.

    A cached .pyc is reused whenever the source's size and whole-second mtime
    match the ones it recorded, so an edit of the same length made within the
    same second would have the gate grade the previous version of the code.
    """

    def get_code(self, fullname):
        return self.source_to_code(self.get_data(self.path), self.path)


def load_module(path: str):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(
        name, path, loader=_FromSource(name, path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_one(path: str, snapshot: dict, extend_to: int | None = None) -> Result:
    seq_id = os.path.splitext(os.path.basename(path))[0].upper()
    started = time.time()
    try:
        mod = load_module(path)
        published = list(mod.PUBLISHED)
        offset = int(mod.OFFSET)
    except Exception as exc:                                  # noqa: BLE001
        return Result(seq_id, False, f"module will not load: {exc!r}")

    if not published:
        return Result(seq_id, False, "module declares no published terms")

    # 1. Does the module agree with OEIS about what OEIS says?
    snap = snapshot.get(seq_id, {}).get("data")
    if snap is None:
        return Result(seq_id, False,
                      "no snapshot of the published data; run `snapshot` first",
                      len(published))
    if list(snap) != published:
        return Result(seq_id, False,
                      f"module's PUBLISHED disagrees with the OEIS snapshot "
                      f"({len(published)} vs {len(snap)} terms)", len(published))

    # 2. Does it reproduce them, and get as far as it says it can?
    #
    # EXTEND_TO is the index the module claims to reach. It matters that the
    # gate recomputes up to it rather than reading a stored answer: a list of
    # new terms sitting in a file is a number somebody typed, while a list the
    # verifier just derived is a result. Modules set it to what runs in CI
    # time, so the published extension is the reproducible one.
    declared = getattr(mod, "EXTEND_TO", None)
    if extend_to is None and declared is not None:
        extend_to = int(declared)
    target = extend_to if extend_to is not None else offset + len(published) - 1
    try:
        got = list(mod.terms(target))
    except Exception as exc:                                  # noqa: BLE001
        return Result(seq_id, False, f"terms() raised: {exc!r}", len(published))
    elapsed = time.time() - started

    if len(got) < len(published):
        return Result(seq_id, False,
                      f"returned {len(got)} terms, fewer than the {len(published)} "
                      f"published", len(published), len(got), [], elapsed)

    # terms(n) is defined to return a(OFFSET)..a(n), so a module asked for an
    # index must deliver up to it. Without this a module could declare
    # EXTEND_TO far ahead, return only the published range, and pass with zero
    # new terms -- correct-looking, silently under-delivering, and impossible to
    # tell apart from a sequence that genuinely resists extension.
    expected = target - offset + 1
    if len(got) != expected:
        return Result(seq_id, False,
                      f"asked for a({offset})..a({target}) = {expected} terms, "
                      f"returned {len(got)}", len(published), len(got), [],
                      elapsed)

    head = got[:len(published)]
    if head != published:
        bad = next(i for i, (a, b) in enumerate(zip(head, published, strict=True)) if a != b)
        return Result(seq_id, False,
                      f"disagrees with OEIS at a({offset + bad}): computed "
                      f"{head[bad]}, published {published[bad]}",
                      len(published), len(got), [], elapsed)

    # 3. Everything past the published data is the contribution.
    return Result(seq_id, True, "reproduces every published term",
                  len(published), len(got), got[len(published):], elapsed, offset)


def check_all(seq_dir: str, snapshot_path: str,
              extend_to: dict[str, int] | None = None) -> list[Result]:
    snapshot = {}
    if os.path.exists(snapshot_path):
        with open(snapshot_path, encoding="utf-8") as fh:
            snapshot = json.load(fh).get("sequences", {})
    paths = sorted(os.path.join(seq_dir, f) for f in os.listdir(seq_dir)
                   if f.startswith("a") and f.endswith(".py"))
    out = []
    for p in paths:
        sid = os.path.splitext(os.path.basename(p))[0].upper()
        out.append(check_one(p, snapshot, (extend_to or {}).get(sid)))
    return out


def snapshot(seq_dir: str, out_path: str) -> dict:
    """Record what OEIS publishes today, so verification is reproducible."""
    ids = sorted(os.path.splitext(f)[0].upper() for f in os.listdir(seq_dir)
                 if f.startswith("a") and f.endswith(".py"))
    seqs, failed = {}, []
    for sid in ids:
        data = fetch_published(sid)
        if data is None:
            failed.append(sid)
        else:
            seqs[sid] = {"data": data, "n_terms": len(data)}
        time.sleep(0.5)                       # be a polite client
    doc = {"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "source": "https://oeis.org/search?q=id:<A-number>&fmt=json",
           "sequences": seqs}
    if failed:
        doc["failed"] = failed
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    return doc


# --------------------------------------------------------------------------
# Confirmation: does the OEIS now publish what this repository computed?
#
# Before the extensions were accepted this check did not exist, and `--live`
# only asked whether the snapshot had gone stale. Acceptance inverts the
# question. The terms are out there now, under a human author's name, and the
# failure mode worth catching is no longer "OEIS moved" but "what got published
# is not what was computed" -- an editor trimming a term, a b-file pasted a line
# off, a submission built from a stale run. Nobody would notice that from the
# inside: this repository would keep passing its own gate while the OEIS carried
# a wrong value attributed to it.
#
# So the live data is compared against the frozen baseline PLUS the terms the
# gate just recomputed, and every way that can disagree gets its own verdict
# rather than one undifferentiated "drift". "The live data" is the b-file,
# which is where an extension longer than DATA_CAP is published and which
# carries its own indices to get wrong (a check of DATA alone would confirm the
# head of such an extension and never see the rest), and the DATA field, which
# a b-file the OEIS synthesized from the entry already is. See confirm_live.
#
#   CONFIRMED   OEIS carries some or all of this repository's terms, all equal.
#   AHEAD       all of them, and more past them -- somebody extended further.
#   PENDING     still only the baseline. Submitted-not-yet-approved looks like
#               this, and so does never-submitted; it is not a failure.
#   CONFIRMED / AHEAD / PENDING are the three states that are not a problem.
#   MISMATCH    OEIS and this repository disagree on a term past the baseline.
#   REVISED     OEIS changed a term, or the offset, the gate verified against. The
#               baseline is no longer what the OEIS says, so the evidence needs
#               re-reading by a human before anything here is a claim again.
#   UNREACHABLE could not fetch or read. Default-deny: not confirmed is not
#               confirmed.
# --------------------------------------------------------------------------

LIVE_OK = ("CONFIRMED", "AHEAD", "PENDING")

# When the DATA field and the b-file both fail, the verdict reported is the one
# a human most needs to act on.
LIVE_SEVERITY = ("MISMATCH", "REVISED", "UNREACHABLE")

# The OEIS shows the DATA field as about three lines, roughly 260 characters of
# comma-separated terms; past that an extension has to travel as a b-file (a
# plain "n a(n)" text file linked from the entry). This is a display limit read
# off the rendered entries, not a validated field width, so it is used only to
# say which extensions certainly need a b-file -- never to conclude that one
# without a b-file would be refused. A b-file is welcome at any length.
DATA_CAP = 260


@dataclasses.dataclass
class LiveResult:
    seq_id: str
    status: str
    detail: str
    n_live: int = 0
    n_confirmed: int = 0

    @property
    def ok(self) -> bool:
        return self.status in LIVE_OK


def confirm_one(seq_id: str, offset: int, baseline: list[int],
                contributed: list[int], live: list[int] | None) -> LiveResult:
    """Classify the live OEIS data against baseline + what the gate computed."""
    if live is None:
        return LiveResult(seq_id, "UNREACHABLE", "could not fetch from OEIS")

    n = len(baseline)
    if live[:n] != baseline:
        if len(live) < n:
            return LiveResult(seq_id, "REVISED",
                              f"OEIS now publishes {len(live)} terms, fewer than the "
                              f"{n} in the frozen baseline", len(live))
        bad = next(i for i, (a, b) in enumerate(zip(live[:n], baseline, strict=True))
                   if a != b)
        return LiveResult(seq_id, "REVISED",
                          f"OEIS changed a({offset + bad}): baseline {baseline[bad]}, "
                          f"now {live[bad]}", len(live))

    extra = live[n:]
    if not extra:
        return LiveResult(seq_id, "PENDING",
                          "OEIS publishes only the baseline terms; nothing from here "
                          "is live yet", len(live))

    for i, (theirs, ours) in enumerate(zip(extra, contributed, strict=False)):
        if theirs != ours:
            return LiveResult(seq_id, "MISMATCH",
                              f"OEIS publishes a({offset + n + i}) = {theirs}, this "
                              f"repository computes {ours}", len(live), i)

    if len(extra) <= len(contributed):
        return LiveResult(seq_id, "CONFIRMED",
                          f"{len(extra)} of this repository's {len(contributed)} terms "
                          f"are published, all equal", len(live), len(extra))
    return LiveResult(seq_id, "AHEAD",
                      f"all {len(contributed)} of this repository's terms are published "
                      f"and equal; OEIS carries {len(extra) - len(contributed)} more "
                      f"past them", len(live), len(contributed))


# The comment the OEIS puts at the head of a b-file it generated from the
# entry's DATA field, because none was uploaded.
SYNTHESIZED = "b-file synthesized from sequence entry"


def is_synthesized(text: str) -> bool:
    """Whether the OEIS rendered this b-file from the entry's DATA field."""
    return any(line.startswith("#") and SYNTHESIZED in line
               for line in text.splitlines())


def parse_bfile(text: str) -> list[tuple[int, int]]:
    """Read a b-file into its (n, a(n)) pairs, in file order.

    One "n a(n)" pair per line; blank lines and lines starting with # are
    skipped. Any other line is a ValueError naming it, not a skipped line: a
    reader that drops what it cannot parse reads a damaged b-file as a shorter,
    intact one.
    """
    pairs = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        try:
            if len(fields) != 2:
                raise ValueError
            pairs.append((int(fields[0]), int(fields[1])))
        except ValueError:
            raise ValueError(f"line {lineno} is not 'n a(n)': {line[:40]!r}") from None
    if not pairs:
        raise ValueError("no 'n a(n)' lines in it")
    return pairs


def confirm_bfile(seq_id: str, offset: int, baseline: list[int],
                  contributed: list[int], text: str | None) -> LiveResult:
    """confirm_one for the b-file, whose indices have to be right as well.

    The DATA field is a bare list, so a term in the wrong place there is simply
    a wrong term. A b-file states every index, and those can be wrong on their
    own: starting from a different offset than the one every a(n) here is
    numbered from, or skipping a line. Both are checked before the values are.
    """
    if text is None:
        return LiveResult(seq_id, "UNREACHABLE", "could not fetch the b-file from OEIS")
    try:
        pairs = parse_bfile(text)
    except ValueError as exc:
        return LiveResult(seq_id, "UNREACHABLE", f"could not read the b-file: {exc}")
    if pairs[0][0] != offset:
        return LiveResult(seq_id, "REVISED",
                          f"the OEIS b-file starts at a({pairs[0][0]}); the gate "
                          f"verified from a({offset})", len(pairs))
    for i, (n, _) in enumerate(pairs):
        if n != offset + i:
            # Inside the baseline this is the record the gate verified against
            # changing under it; past it, a term here with no row there.
            return LiveResult(seq_id, "REVISED" if i < len(baseline) else "MISMATCH",
                              f"the OEIS b-file goes from a({offset + i - 1}) to "
                              f"a({n})", len(pairs))
    return confirm_one(seq_id, offset, baseline, contributed, [v for _, v in pairs])


def _one_verdict(data: LiveResult, table: LiveResult) -> LiveResult:
    """Fold the DATA-field and b-file verdicts for one entry into one.

    Both have to pass. A failure of either is the verdict (the more serious one
    if both fail, with both reasons); otherwise the source carrying more of
    this repository's terms speaks for the entry, which for a long extension is
    the b-file.
    """
    data = dataclasses.replace(data, detail=f"DATA: {data.detail}")
    table = dataclasses.replace(table, detail=f"b-file: {table.detail}")
    bad = [x for x in (data, table) if not x.ok]
    if bad:
        worst = min(bad, key=lambda x: LIVE_SEVERITY.index(x.status))
        return dataclasses.replace(worst, detail="; ".join(x.detail for x in bad))
    return max((data, table), key=lambda x: (x.n_confirmed, x.n_live))


def confirm_live(results: list[Result], snapshot: dict, fetch=None, fetch_b=None,
                 pause: float = 0.5) -> list[LiveResult]:
    """Check every sequence the offline gate passed against what the OEIS
    publishes: its b-file (fetched by `fetch_b`) and its DATA field (`fetch`).

    The b-file comes first. Where the OEIS synthesized it from the entry, it is
    the DATA field with indices added, so checking it checks both and the DATA
    field is not fetched again. That matters: the search endpoint the DATA
    field comes from answers automated clients with a bot challenge (HTTP 403
    from GitHub's runners), while b-files are served. Where the b-file was
    uploaded, the DATA field is a separate record, and it is fetched and
    checked as well.

    A sequence that failed the gate is left out rather than reported as
    unconfirmed: its own failure is already the answer, and re-stating it as a
    second red line invites fixing the wrong thing.
    """
    fetch = fetch or fetch_published
    fetch_b = fetch_b or fetch_bfile
    out = []
    for r in results:
        if not r.ok:
            continue
        baseline = list(snapshot.get(r.seq_id, {}).get("data") or [])
        ours = list(r.new_terms)
        text = fetch_b(r.seq_id)
        if pause:
            time.sleep(pause)                 # be a polite client
        table = confirm_bfile(r.seq_id, r.offset, baseline, ours, text)
        if text is not None and is_synthesized(text):
            out.append(dataclasses.replace(
                table, detail=f"b-file, synthesized from DATA: {table.detail}"))
            continue
        data = confirm_one(r.seq_id, r.offset, baseline, ours, fetch(r.seq_id))
        if pause:
            time.sleep(pause)
        out.append(_one_verdict(data, table))
    return out


def data_line(terms: list[int]) -> str:
    """The terms as the OEIS DATA field renders them."""
    return ", ".join(str(t) for t in terms)


def fits_in_data(terms: list[int]) -> bool:
    return len(data_line(terms)) <= DATA_CAP


def bfile_text(seq_id: str, offset: int, terms: list[int]) -> str:
    """Render a b-file: one "n a(n)" line per term, LF endings, no blank last line.

    The header comment is the form the OEIS itself generates. Note that this is
    rendered from the terms the gate just recomputed, never from a stored list:
    a b-file assembled by hand from an old run is exactly the transcription
    error `verify --live` exists to catch, and generating it from anything but
    the verified output would build that error in at the source.
    """
    last = offset + len(terms) - 1
    head = f"# {seq_id}: Table of n, a(n) for n = {offset}..{last}.\n"
    return head + "".join(f"{offset + i} {t}\n" for i, t in enumerate(terms))
