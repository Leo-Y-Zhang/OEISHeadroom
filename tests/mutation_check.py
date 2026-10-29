"""Reproduce the targeted mutation experiment (not part of pytest collection).

Run with Python: tests/mutation_check.py before|after --output FILE --cache FILE.
Each edit is applied alone in a temporary copy; project sources are never edited.
The offline gate replays the original terms() outputs for *unchanged* sequence
sources, checked by SHA256. A changed sequence is always recomputed. This avoids
repeating expensive, unrelated algorithms while retaining the real CLI, loader,
snapshot, length, value and exit-status checks. Cache creation runs the full gate.
The second gate invocation corrupts the first computed value, as CI does, and
must fail. It reuses the values observed during the first invocation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# id, module, exact source fragment, replacement. No syntax-error mutants.
MUTATIONS = [
    ("V01", "oeisheadroom/verify.py", "if list(snap) != published:", "if False:"),
    ("V02", "oeisheadroom/verify.py", "if head != published:", "if False:"),
    ("V03", "oeisheadroom/verify.py", "if len(got) != expected:", "if len(got) < expected:"),
    ("V04", "oeisheadroom/verify.py", "target - offset + 1", "target - offset - 1"),
    ("V05", "oeisheadroom/verify.py", "if extend_to is None and declared is not None:", "if extend_to is None or declared is not None:"),
    ("V06", "oeisheadroom/verify.py", "if theirs != ours:", "if False:"),
    ("V07", "oeisheadroom/verify.py", "if len(extra) <= len(contributed):", "if len(extra) < len(contributed):"),
    ("V08", "oeisheadroom/verify.py", "if len(fields) != 2:", "if len(fields) < 2:"),
    ("V09", "oeisheadroom/verify.py", "if n != offset + i:", "if False:"),
    ("V10", "oeisheadroom/verify.py", 'line.startswith("#") and SYNTHESIZED in line', 'line.startswith("#") or SYNTHESIZED in line'),
    ("V11", "oeisheadroom/verify.py", "worst = min(bad,", "worst = max(bad,"),
    ("V12", "oeisheadroom/verify.py", 'if f.startswith("a") and f.endswith(".py"))\n    out = []', 'if f.startswith("a") or f.endswith(".py"))\n    out = []'),
    ("V13", "oeisheadroom/verify.py", "got[len(published):], elapsed, offset", "got[len(published) - 1:], elapsed, offset"),
    ("V14", "oeisheadroom/verify.py", "last = offset + len(terms) - 1", "last = offset + len(terms) + 1"),
    ("V15", "oeisheadroom/verify.py", '(extend_to or {}).get(sid)', '(extend_to or {}).get("missing")'),
    ("V16", "oeisheadroom/verify.py", "if live[:n] != baseline:", "if live[:n - 1] != baseline[:-1]:"),
    ("C01", "oeisheadroom/__main__.py", "    if failed:\n", "    if False:\n"),
    ("C02", "oeisheadroom/__main__.py", "    if live_failed:\n", "    if False:\n"),
    ("C03", "oeisheadroom/__main__.py", "        if not r.ok:\n", "        if False:\n"),
    ("C04", "oeisheadroom/__main__.py", "            if have != text:\n", "            if False:\n"),
    ("C05", "oeisheadroom/__main__.py", "            if have != text:\n", "            if have == text:\n"),
    ("C06", "oeisheadroom/__main__.py", 'full = list(snap.get(r.seq_id, {}).get("data") or []) + list(r.new_terms)', 'full = list(snap.get(r.seq_id, {}).get("data") or [])'),
    ("S01", "oeisheadroom/survey.py", "MIN_TERMS <= len(terms) <= MAX_TERMS", "MIN_TERMS < len(terms) <= MAX_TERMS"),
    ("S02", "oeisheadroom/survey.py", "MIN_TERMS <= len(terms) <= MAX_TERMS", "MIN_TERMS <= len(terms) < MAX_TERMS"),
    ("S03", "oeisheadroom/survey.py", "MIN_LAST <= last < MAX_LAST", "MIN_LAST < last < MAX_LAST"),
    ("S04", "oeisheadroom/survey.py", "if growth > MAX_GROWTH:", "if growth >= MAX_GROWTH:"),
    ("S05", "oeisheadroom/survey.py", "last != max(terms) or", "False or"),
    ("S06", "oeisheadroom/survey.py", 'data.strip().strip(",")', 'data.strip()'),
    ("S07", "oeisheadroom/survey.py", "if aid in seqs:", "if aid not in seqs:"),
    ("T01", "sequences/a319381.py", "if N == 1:", "if N == 0:"),
    ("T02", "sequences/a319381.py", "if s2 < M:", "if s2 < M - 1:"),
    ("T03", "sequences/a319381.py", "& COEFF) + out[-1]", "& COEFF) - out[-1]"),
    ("P01", "sequences/a323586.py", "if n == 0:", "if n == -1:"),
    ("P02", "sequences/a323586.py", "if m == 0:", "if m == 1:"),
    ("P03", "sequences/a323586.py", "cap // (i + 1)", "cap // (i + 2)"),
    ("N01", "sequences/a325555.py", "if used[d]:", "if not used[d]:"),
    ("N02", "sequences/a325555.py", "row[s] += row[s - k]", "row[s] += row[s - k + 1]"),
    ("N03", "sequences/a325555.py", "if any(row)}", "if all(row)}"),
    ("N04", "sequences/a325555.py", "used[abs(prefix[i + 1] - prefix[i])] = 1", "used[abs(prefix[i + 1] - prefix[i])] = 0"),
    ("D01", "sequences/a325556.py", "delta != v and not used[delta] and not used[v]", "delta != v and not used[delta]"),
    ("D02", "sequences/a325556.py", "first < lo or first > hi", "first <= lo or first >= hi"),
    ("D03", "sequences/a325556.py", "res = list(base)\n    for k in ks:", "res = [0] * (n_max + 1)\n    for k in ks:"),
    ("U01", "sequences/a337114.py", "if rem == 0:", "if rem == 1:"),
    ("U02", "sequences/a337114.py", "ways = CAP\n                    break", "ways = CAP - 1\n                    break"),
    ("U03", "sequences/a337114.py", "if c >= 2:", "if c > 2:"),
    ("U04", "sequences/a337114.py", "ways *= comb(rem, t)", "ways *= comb(rem, t) + 1"),
    ("F01", "sequences/a347414.py", "if k == 1:\n        return code", "if k == 1:\n        return 0"),
    ("F02", "sequences/a347414.py", "if depth == cc:", "if depth == cc - 1:"),
    ("F03", "sequences/a347414.py", "if j > c:", "if j >= c:"),
    ("R01", "sequences/a353403.py", "while c and bl[j] == vv:", "while c and bl[j] != vv:"),
    ("R02", "sequences/a353403.py", "if n <= 0:\n        return 1 if n == 0 else 0", "if n <= 0:\n        return 0"),
    ("R03", "sequences/a353403.py", "range(idx, len(tasks), nworkers)", "range(idx + 1, len(tasks), nworkers)"),
    ("R04", "sequences/a353403.py", "c = bl[0] - 1", "c = bl[0] - 2"),
]

GATE = '''
import hashlib, json, pathlib, sys
from oeisheadroom import verify, __main__ as cli
cache_path = pathlib.Path(sys.argv[1])
cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
recording = not cache
original = verify.load_module
observed = {}
sabotage = False
first = sorted(pathlib.Path("sequences").glob("a*.py"))[0].name
def load(path):
    mod = original(path)
    key = pathlib.Path(path).name
    digest = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    saved = cache.get(key)
    terms = mod.terms
    def run(target):
        if sabotage:
            values = list(observed[key])
            if key == first:
                values[0] += 1
        elif saved and saved["sha256"] == digest and saved["target"] == target:
            values = list(saved["terms"])
        else:
            values = list(terms(target))
            if recording:
                cache[key] = {"sha256": digest, "target": target, "terms": values}
        if not sabotage:
            observed[key] = list(values)
        return values
    mod.terms = run
    return mod
verify.load_module = load
rc = cli.main(["verify"])
if rc == 0:
    sabotage = True
    if cli.main(["verify"]) == 0:
        rc = 1  # CI must reject a gate that accepted the corrupted term.
if recording and rc == 0:
    cache_path.write_text(json.dumps(cache))
sys.exit(rc)
'''


def run(command, cwd):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"outcome": "timeout"}
    return {"outcome": "passed" if result.returncode == 0 else "killed",
            "returncode": result.returncode}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["before", "after"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cache = args.cache.resolve()
    doc = json.loads(args.output.read_text()) if args.output.exists() else {}
    scratch = root / ".ruff_cache"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mutation-", dir=scratch) as tmp:
        work = Path(tmp)
        for directory in ("oeisheadroom", "sequences", "tests"):
            shutil.copytree(root / directory, work / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "mutation_*.json"))
        shutil.copyfile(root / "published.json", work / "published.json")
        gate = [sys.executable, "-B", "-c", GATE, str(cache)]
        tests = ([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"]
                 if args.phase == "before" else [sys.executable, "-B", "-m", "pytest", "-q"])
        assert run(tests, work)["outcome"] == "passed", "unmutated tests failed"
        assert run(gate, work)["outcome"] == "passed", "unmutated gate failed"
        for mid, module, old, new in MUTATIONS:
            path = work / module
            source = path.read_bytes()
            text = source.decode().replace("\r\n", "\n")
            assert old in text, (mid, "mutation fragment missing")
            changed = text.replace(old, new, 1)
            compile(changed, module, "exec")
            path.write_bytes(changed.encode("utf-8"))
            try:
                unit = run(tests, work)
                measured_gate = (run(gate, work) if unit["outcome"] == "passed"
                                 else {"outcome": "not run (tests killed)"})
                row = doc.setdefault(mid, {"module": module, "old": old, "new": new})
                row[args.phase] = {"tests": unit, "gate": measured_gate}
                row[args.phase]["killed"] = (unit["outcome"] == "killed"
                                            or measured_gate["outcome"] == "killed")
                print(f"{args.phase} {mid}: tests={unit['outcome']}, "
                      f"gate={measured_gate['outcome']}", flush=True)
                args.output.write_text("{\n" + ",\n".join(
                    f"  {json.dumps(key)}: {json.dumps(value)}" for key, value in doc.items())
                    + "\n}\n")
            finally:
                path.write_bytes(source)
    # Keep a checksum in the results so the mutation set is unambiguous.
    digest = hashlib.sha256(json.dumps(MUTATIONS).encode()).hexdigest()
    print(f"mutation set SHA256: {digest}")


if __name__ == "__main__":
    main()
