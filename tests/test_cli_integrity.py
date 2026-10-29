"""Exercise the CLI's rejection and export checks with a tiny real module."""

import json

import pytest

from oeisheadroom import __main__ as cli
from oeisheadroom import verify

BASE = [2, 3, 5]
FULL = [2, 3, 5, 7, 11]
BFILE = "# A000001: Table of n, a(n) for n = 0..4.\n0 2\n1 3\n2 5\n3 7\n4 11\n"


@pytest.fixture
def project(tmp_path, monkeypatch):
    seqs = tmp_path / "sequences"
    seqs.mkdir()
    module = seqs / "a000001.py"
    module.write_text(
        f"OFFSET = 0\nPUBLISHED = {BASE!r}\nEXTEND_TO = 4\n"
        f"def terms(n):\n    return {FULL!r}[:n + 1]\n", encoding="utf-8")
    snapshot = tmp_path / "published.json"
    snapshot.write_text(json.dumps({"fetched_utc": "2000-01-01T00:00:00Z",
                                   "sequences": {"A000001": {"data": BASE}}}),
                        encoding="utf-8")
    out = tmp_path / "exports"
    monkeypatch.setattr(cli, "SEQ_DIR", str(seqs))
    monkeypatch.setattr(cli, "SNAPSHOT", str(snapshot))
    monkeypatch.setattr(cli, "BFILE_DIR", str(out))

    def no_fetch(*args, **kwargs):
        pytest.fail("unit tests must not fetch network data")

    monkeypatch.setattr(verify, "_get", no_fetch)
    monkeypatch.setattr(verify.time, "sleep", lambda _: None)
    return module, snapshot, out


def test_real_gate_accepts_valid_module_and_ignores_non_sequence_files(project, capsys):
    module, snapshot, _ = project
    (module.parent / "helper.py").write_text("raise RuntimeError('not a sequence')\n")
    (module.parent / "a000002.txt").write_text("not Python\n")
    results = verify.check_all(str(module.parent), str(snapshot))
    assert len(results) == 1
    assert results[0].ok
    assert (results[0].n_published, results[0].n_computed, results[0].offset) == (3, 5, 0)
    assert results[0].new_terms == [7, 11]
    assert cli.main(["verify"]) == 0
    assert "1/1 sequences" in capsys.readouterr().out


@pytest.mark.parametrize("values", [[2, 4, 5, 7, 11], [2, 3], [2, 3, 5], FULL + [13]])
def test_gate_rejects_changed_value_and_wrong_counts(project, values, capsys):
    module, _, _ = project
    source = module.read_text()
    module.write_text(source.replace(f"return {FULL!r}[:n + 1]", f"return {values!r}"))
    assert cli.main(["verify"]) == 1
    assert "1 FAILED" in capsys.readouterr().out


def test_gate_rejects_removed_snapshot_value(project):
    _, snapshot, _ = project
    snapshot.write_text(json.dumps({"sequences": {"A000001": {"data": BASE[:-1]}}}))
    assert cli.main(["verify"]) == 1


def test_bfile_writes_verified_extension_and_checks_it(project):
    _, _, out = project
    assert cli.main(["bfile"]) == 0
    path = out / "b000001.txt"
    assert path.read_bytes() == BFILE.encode()
    assert cli.main(["bfile", "--check"]) == 0
    assert path.read_bytes() == BFILE.encode()


@pytest.mark.parametrize("damaged", [
    BFILE.replace("3 7", "3 8"),       # one changed value
    BFILE.replace("2 5\n", ""),      # a removed row
    BFILE.replace("3 7", "9 7"),       # one changed index
    BFILE.rsplit("4 11", 1)[0],         # truncated at the last row
    BFILE + "5 13\n",                  # wrong count
    None,                              # missing file
])
def test_bfile_check_rejects_corruption_without_rewriting(project, damaged):
    _, _, out = project
    out.mkdir()
    path = out / "b000001.txt"
    if damaged is not None:
        path.write_text(damaged)
    assert cli.main(["bfile", "--check"]) == 1
    if damaged is None:
        assert not path.exists()
    else:
        assert path.read_text() == damaged


def test_bfile_refuses_failed_sequence_and_preserves_existing_export(project):
    module, _, out = project
    module.write_text(module.read_text().replace(f"return {FULL!r}", "return [99, 3, 5, 7, 11]"))
    out.mkdir()
    path = out / "b000001.txt"
    path.write_text("previous export\n")
    assert cli.main(["bfile"]) == 1
    assert path.read_text() == "previous export\n"


@pytest.mark.parametrize("body, data, status", [
    (BFILE, FULL, "CONFIRMED"),
    (BFILE.replace("3 7", "3 8"), FULL, "MISMATCH"),
    (BFILE, [2, 3, 5, 8, 11], "MISMATCH"),
    (BFILE.replace("1 3\n", ""), FULL, "REVISED"),
    ("0 2\n1 3\n", FULL, "REVISED"),  # truncated inside baseline
    (BFILE + "5", FULL, "UNREACHABLE"),  # truncated mid-row
    (None, FULL, "UNREACHABLE"),
])
def test_live_cli_failure_changes_exit_status(project, monkeypatch, capsys, body, data, status):
    monkeypatch.setattr(verify, "fetch_bfile", lambda _: body)
    monkeypatch.setattr(verify, "fetch_published", lambda _: data)
    assert cli.main(["verify", "--live"]) == (0 if status == "CONFIRMED" else 1)
    assert status in capsys.readouterr().out
