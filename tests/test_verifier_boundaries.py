"""Boundary corruptions that must not become successful verdicts."""

import json

import pytest

from oeisheadroom import verify


def test_check_all_applies_per_sequence_target_override(tmp_path):
    (tmp_path / "a000001.py").write_text(
        "OFFSET = 0\nPUBLISHED = [2, 3]\nEXTEND_TO = 3\n"
        "def terms(n):\n    return [2, 3, 5, 7][:n + 1]\n")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"sequences": {"A000001": {"data": [2, 3]}}}))
    results = verify.check_all(str(tmp_path), str(snapshot), {"A000001": 2})
    assert len(results) == 1
    assert results[0].ok
    assert results[0].new_terms == [5]
    assert results[0].n_computed == 3


@pytest.mark.parametrize("live", [[2, 3, 99, 7], [2, 3]])
def test_last_baseline_value_and_one_row_truncation_are_checked(live):
    valid = verify.confirm_one("A000001", -1, [2, 3, 5], [7], [2, 3, 5, 7])
    assert valid.ok
    assert (valid.status, valid.n_confirmed) == ("CONFIRMED", 1)
    result = verify.confirm_one("A000001", -1, [2, 3, 5], [7], live)
    assert not result.ok
    assert result.status == "REVISED"


@pytest.mark.parametrize("offset", [-2, 0, 1])
def test_bfile_round_trip_and_single_value_or_row_corruptions(offset):
    text = verify.bfile_text("A000001", offset, [2, 3, 5, 7])
    assert verify.parse_bfile(text) == [(offset + i, v) for i, v in enumerate([2, 3, 5, 7])]
    good = verify.confirm_bfile("A000001", offset, [2, 3, 5], [7], text)
    assert good.ok
    assert good.n_confirmed == 1
    for damaged in (text.replace(f"{offset + 2} 5\n", f"{offset + 2} 99\n"),
                    text.replace(f"{offset + 2} 5\n", ""),
                    text[:text.index(f"{offset + 2} 5\n")]):
        result = verify.confirm_bfile("A000001", offset, [2, 3, 5], [7], damaged)
        assert not result.ok
        assert result.status == "REVISED"


def test_ordinary_comment_cannot_make_an_uploaded_bfile_stand_in_for_data():
    result = verify.Result("A000001", True, "ok", new_terms=[7], offset=0)
    body = "# uploaded table\n0 2\n1 3\n2 5\n3 7\n"
    calls = []

    def fetch(sid):
        calls.append(sid)
        return [2, 3, 5, 99]

    results = verify.confirm_live([result], {"A000001": {"data": [2, 3, 5]}},
                                  fetch=fetch, fetch_b=lambda _: body, pause=0)
    assert calls == ["A000001"]
    assert len(results) == 1
    assert not results[0].ok
    assert results[0].status == "MISMATCH"
