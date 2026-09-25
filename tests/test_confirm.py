"""Tests for the confirmation check and the b-file renderer.

`verify` asks whether this repository is right. `verify --live` asks a question
that only exists now that the extensions were accepted: whether what the OEIS
publishes is what was computed here. The interesting cases are the ones where
the answer is no, because that is a wrong value in the OEIS under a human's
name, and because a check that cannot distinguish "not approved yet" from "the
published value disagrees with mine" would report both as drift and train its
reader to ignore it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oeisheadroom import verify  # noqa: E402
from oeisheadroom.verify import (  # noqa: E402
    Result,
    bfile_text,
    confirm_live,
    confirm_one,
    data_line,
    fetch_published,
    fits_in_data,
)

BASE = [1, 2, 3, 5, 8]
OURS = [13, 21, 34]


def confirm(live, baseline=BASE, ours=OURS, offset=1):
    return confirm_one("A000001", offset, baseline, ours, live)


class TestConfirms(unittest.TestCase):
    def test_all_of_our_terms_published_and_equal_is_confirmed(self):
        r = confirm(BASE + OURS)
        self.assertEqual(r.status, "CONFIRMED")
        self.assertEqual(r.n_confirmed, 3)
        self.assertTrue(r.ok)

    def test_a_partially_approved_extension_confirms_what_is_there(self):
        """Editors approve in batches; two of three terms live is not a fault."""
        r = confirm(BASE + OURS[:2])
        self.assertEqual(r.status, "CONFIRMED")
        self.assertEqual(r.n_confirmed, 2)

    def test_terms_past_ours_are_reported_but_not_a_failure(self):
        r = confirm(BASE + OURS + [55, 89])
        self.assertEqual(r.status, "AHEAD")
        self.assertEqual(r.n_confirmed, 3)
        self.assertTrue(r.ok)
        self.assertIn("2 more", r.detail)

    def test_nothing_published_past_the_baseline_is_pending_not_drift(self):
        r = confirm(BASE)
        self.assertEqual(r.status, "PENDING")
        self.assertTrue(r.ok)


class TestRefuses(unittest.TestCase):
    def test_a_published_term_disagreeing_with_ours_is_a_mismatch(self):
        """The failure this check exists for: a wrong value live in the OEIS."""
        r = confirm(BASE + [13, 22, 34])
        self.assertEqual(r.status, "MISMATCH")
        self.assertFalse(r.ok)
        # baseline is a(1)..a(5); the second contributed term is a(7).
        self.assertIn("a(7)", r.detail)
        self.assertIn("22", r.detail)
        self.assertIn("21", r.detail)

    def test_the_mismatched_index_follows_the_offset(self):
        r = confirm(BASE + [13, 22, 34], offset=0)
        self.assertIn("a(6)", r.detail)

    def test_a_changed_baseline_term_is_revised_not_mismatch(self):
        """OEIS correcting data the gate verified against invalidates the gate."""
        r = confirm([1, 2, 4, 5, 8] + OURS)
        self.assertEqual(r.status, "REVISED")
        self.assertFalse(r.ok)
        self.assertIn("a(3)", r.detail)

    def test_a_shortened_entry_is_revised(self):
        r = confirm([1, 2, 3])
        self.assertEqual(r.status, "REVISED")
        self.assertFalse(r.ok)

    def test_unreachable_is_a_failure_not_a_skip(self):
        """Default-deny: not confirmed and cannot-check must not look alike."""
        r = confirm(None)
        self.assertEqual(r.status, "UNREACHABLE")
        self.assertFalse(r.ok)


class TestConfirmLive(unittest.TestCase):
    def snapshot(self):
        return {"A000001": {"data": BASE, "n_terms": len(BASE)}}

    def result(self, ok=True):
        return Result("A000001", ok, "reproduces every published term",
                      len(BASE), len(BASE) + len(OURS), list(OURS), 0.0, 1)

    def test_fetches_and_classifies_each_passing_sequence(self):
        out = confirm_live([self.result()], self.snapshot(),
                           fetch=lambda sid: BASE + OURS, pause=0)
        self.assertEqual([r.status for r in out], ["CONFIRMED"])

    def test_a_sequence_that_failed_the_gate_is_not_reported_twice(self):
        calls = []

        def fetch(sid):
            calls.append(sid)
            return BASE

        out = confirm_live([self.result(ok=False)], self.snapshot(),
                           fetch=fetch, pause=0)
        self.assertEqual(out, [])
        self.assertEqual(calls, [])           # and it does not hit the network


def served(body: bytes, returncode: int = 0):
    """Stand in for curl: every fetch returns this body and exit status."""
    done = subprocess.CompletedProcess([], returncode, stdout=body, stderr=b"")
    return mock.patch.object(verify.subprocess, "run", return_value=done)


class TestFetchPublished(unittest.TestCase):
    """fetch_published promises a list of terms or None, never an exception:
    one sequence OEIS will not answer for must come back UNREACHABLE, not take
    the whole confirmation run down with a traceback."""

    def test_reads_the_data_field_of_the_current_list_format(self):
        with served(b'[{"number": 1, "data": "1,2,3,5,8"}]'):
            self.assertEqual(fetch_published("A000001"), [1, 2, 3, 5, 8])

    def test_reads_the_older_results_wrapper(self):
        with served(b'{"count": 1, "results": [{"number": 1, "data": "1,2,3"}]}'):
            self.assertEqual(fetch_published("A000001"), [1, 2, 3])

    def test_no_hit_in_either_format_is_none(self):
        for body in (b"null", b"[]", b'{"count": 0, "results": null}',
                     b'{"count": 0, "results": []}'):
            with self.subTest(body=body), served(body):
                self.assertIsNone(fetch_published("A000001"))

    def test_a_record_without_a_usable_data_field_is_none(self):
        for body in (b'[{"number": 1}]', b'[{"number": 1, "data": 5}]',
                     b'["A000001"]', b'[{"number": 1, "data": "1,x,3"}]'):
            with self.subTest(body=body), served(body):
                self.assertIsNone(fetch_published("A000001"))

    def test_an_error_page_is_none(self):
        with served(b"<html>Too Many Requests</html>"):
            self.assertIsNone(fetch_published("A000001"))

    def test_a_failed_transfer_is_none(self):
        with served(b'[{"number": 1, "data": "1,2,3"}]', returncode=22):
            self.assertIsNone(fetch_published("A000001"))


class TestBfile(unittest.TestCase):
    def test_lines_are_index_and_value_from_the_offset(self):
        text = bfile_text("A000001", 1, [1, 2, 3])
        self.assertEqual(text.splitlines()[1:], ["1 1", "2 2", "3 3"])

    def test_the_header_names_the_range_the_file_actually_covers(self):
        self.assertTrue(bfile_text("A000001", 0, [1, 2, 3]).startswith(
            "# A000001: Table of n, a(n) for n = 0..2.\n"))

    def test_an_offset_of_zero_starts_at_zero(self):
        self.assertEqual(bfile_text("A000001", 0, [7]).splitlines()[1], "0 7")

    def test_data_line_matches_the_oeis_rendering(self):
        self.assertEqual(data_line([1, 2, 3]), "1, 2, 3")

    def test_a_long_extension_is_flagged_as_needing_a_bfile(self):
        self.assertFalse(fits_in_data(list(range(1000, 1100))))

    def test_a_short_one_is_not(self):
        self.assertTrue(fits_in_data([1, 2, 3]))


if __name__ == "__main__":
    unittest.main()
