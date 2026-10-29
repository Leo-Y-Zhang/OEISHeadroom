"""Small offline fixtures for the survey's numeric limits and dump parser."""

import gzip

import pytest

from oeisheadroom import survey

NAME = "Number of trees on n vertices."


@pytest.mark.parametrize("count, last, accepted", [
    (7, 1000, False), (8, 1000, True), (25, 1000, True), (26, 1000, False),
    (8, 999, False), (8, 1001, True),
])
def test_term_count_and_lower_magnitude_endpoints(count, last, accepted):
    data = ",".join(map(str, range(last - count + 1, last + 1)))
    result = survey.assess(NAME, data)
    assert (result is not None) == accepted
    if accepted:
        assert result == {"n_terms": count, "last": last, "growth": 1.0}


def test_growth_cap_is_inclusive_and_compared_before_rounding():
    result = survey.assess(NAME, "100,200,300,400,500,6000,6001,6002")
    assert result == {"n_terms": 8, "last": 6002, "growth": 12.0}
    assert survey.assess(NAME, "100,200,300,400,500,6001,6002,6003") is None


def test_a_large_early_peak_is_not_hidden_by_a_growing_tail():
    assert survey.assess(NAME, "1,0,100,200,400,800,1600,3200") is not None
    assert survey.assess(NAME, "9000,0,100,200,400,800,1600,3200") is None


def test_load_joins_by_id_and_removes_only_dump_delimiters(tmp_path, monkeypatch):
    names = tmp_path / "names.gz"
    stripped = tmp_path / "stripped.gz"
    names.write_bytes(gzip.compress(
        b"# header\nA000001 Number of trees.\nA000002 Name with a bad byte: \xff\n"))
    stripped.write_bytes(gzip.compress(
        b"# header\nA000003 ,99,\nA000001 ,1,-2,300,\n"))
    monkeypatch.setattr(survey, "download", lambda _: {"names": names, "stripped": stripped})
    result = survey.load(str(tmp_path))
    assert result == {
        "A000001": {"id": "A000001", "name": "Number of trees.", "data": "1,-2,300"},
        "A000002": {"id": "A000002", "name": "Name with a bad byte: \ufffd"},
    }
