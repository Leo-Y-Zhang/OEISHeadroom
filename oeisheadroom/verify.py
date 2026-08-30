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
fetched, so `verify` works offline and in CI, while `verify --live` re-fetches
and reports drift. A verifier that silently needs the network is a verifier that
silently stops running.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import subprocess
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

    @property
    def n_new(self) -> int:
        return len(self.new_terms)


def fetch_published(seq_id: str, timeout: int = 60) -> list[int] | None:
    """Pull a sequence's DATA line straight from OEIS. None on any failure.

    Note the explicit utf-8 decode: OEIS records carry accented author names,
    and Windows' cp1252 default raises UnicodeDecodeError on them.
    """
    url = f"https://oeis.org/search?q=id:{seq_id}&fmt=json"
    try:
        out = subprocess.run(["curl", "-s", "-A", UA, url],
                             capture_output=True, timeout=timeout)
        doc = json.loads(out.stdout.decode("utf-8", "replace"))
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None
    rec = doc.get("results", [None])[0] if isinstance(doc, dict) else (
        doc[0] if doc else None)
    if not rec or "data" not in rec:
        return None
    try:
        return [int(x) for x in rec["data"].split(",") if x.strip()]
    except ValueError:
        return None


def load_module(path: str):
    spec = importlib.util.spec_from_file_location(
        os.path.splitext(os.path.basename(path))[0], path)
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
                  len(published), len(got), got[len(published):], elapsed)


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
