"""Tests for the headroom filter.

The filter's two hard-won criteria each get a test named after the mistake it
prevents, because both were live bugs that produced a confident and useless
candidate list before they were caught.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oeisheadroom import survey  # noqa: E402
from oeisheadroom.survey import assess  # noqa: E402

GOOD_NAME = "Number of plane partitions of n with no repeated rows."
GROWING = ",".join(str(v) for v in
                   [1, 2, 5, 12, 30, 76, 195, 504, 1310, 3420, 8964, 23535])


class TestAccepts(unittest.TestCase):
    def test_a_growing_counting_sequence_with_a_small_last_term_is_kept(self):
        got = assess(GOOD_NAME, GROWING)
        self.assertIsNotNone(got)
        self.assertEqual(got["n_terms"], 12)
        self.assertEqual(got["last"], 23535)

    def test_early_wobble_is_tolerated(self):
        """Counting sequences are often flat or erratic at tiny n, before the
        structure being counted has room to exist. Only the tail must grow."""
        wobbly = "1,1,0,0,3,2,5,12,16,30,45,94,159,285,477,864,1487,2643"
        self.assertIsNotNone(assess(
            "Number of compositions of n whose reversed run-lengths appear.",
            wobbly))


class TestRejects(unittest.TestCase):
    def test_an_oscillating_sequence_is_rejected(self):
        """The A375299 lesson, and the reason monotonicity is a criterion.

        "Number of longest winning paths in n X n Hex" runs
        ... 1298, 83648, 16631833, 70630. Counts of maximum-size objects
        oscillate, so the last term says nothing about whether the problem is
        tractable. Keeping these filled the shortlist with noise.
        """
        hexish = ("1,3,1,4,23,51,20,115,5568,12,3521,40,1058,2104,668,"
                  "7540,1298,83648,16631833,70630")
        self.assertIsNone(assess("Number of longest winning paths in n X n Hex.",
                                 hexish))

    def test_a_huge_last_term_is_rejected(self):
        """The Dedekind lesson: few terms means HARD unless the terms are small.

        A first pass keyed on term count alone returned Dedekind numbers,
        posets and polycubes - all famous, all attacked with supercomputers,
        all hopeless. They are short because the answers explode.
        """
        dedekind = ("2,3,6,20,168,7581,7828354,2414682040998,"
                    "56130437228687557907788,"
                    "286386577668298411128469151667598498812366")
        self.assertIsNone(assess("Number of monotone Boolean functions of n "
                                 "variables (graphs).", dedekind))

    def test_explosive_growth_is_rejected(self):
        """Factorial growth outruns any algorithm within a few terms.

        Note the bar is loose on purpose: a sequence tripling each term is
        ordinary for a counting problem and is kept. Only growth that
        accelerates past a constant factor per step is disqualifying.
        """
        import math
        blowup = ",".join(str(math.factorial(k)) for k in range(4, 17))
        self.assertIsNone(assess(GOOD_NAME, blowup))

    def test_steady_geometric_growth_is_kept(self):
        """The guard on the test above: tripling is fine, and must stay fine."""
        tripling = ",".join(str(3 ** k) for k in range(1, 13))
        self.assertIsNotNone(assess(GOOD_NAME, tripling))

    def test_prime_searches_are_excluded_by_name(self):
        self.assertIsNone(assess(
            "Numbers k such that 10*R_k + 3 is prime, where R_k is a repunit.",
            GROWING))

    def test_a_name_with_no_structure_word_is_excluded(self):
        self.assertIsNone(assess("Number of happy things.", GROWING))

    def test_a_name_that_is_not_a_count_is_excluded(self):
        self.assertIsNone(assess("Largest prime factor of the n-th tree.",
                                 GROWING))

    def test_a_triangle_read_by_rows_is_excluded(self):
        """Its 'terms' are a flattened 2D array, so term count and last value
        do not mean what the filter assumes."""
        self.assertIsNone(assess(
            "Triangle read by rows: number of graphs with n nodes and k edges.",
            GROWING))

    def test_too_few_terms_is_rejected(self):
        self.assertIsNone(assess(GOOD_NAME, "1,2,5,12,30"))

    def test_unparseable_data_is_rejected_rather_than_crashing(self):
        self.assertIsNone(assess(GOOD_NAME, "1,2,x,12,30,76,195,504,1310"))


def fake_curl(fail_on=None):
    """Stand in for curl: write 2 MB to the -o target, then, for the dump named
    by fail_on, fail part way through as a timeout or a dropped connection would.
    """
    calls = []

    def run(cmd, **kwargs):
        url = next(a for a in cmd if a.startswith("https://"))
        calls.append(url)
        with open(cmd[cmd.index("-o") + 1], "wb") as fh:
            fh.write(b"\x1f\x8b" + b"\0" * 2_000_000)
        if fail_on and fail_on in url:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
        return subprocess.CompletedProcess(cmd, 0)

    return run, calls


class TestDownload(unittest.TestCase):
    """A cached dump over the size floor is trusted on sight, so nothing but a
    finished download may ever be found at a cache path."""

    def test_an_interrupted_download_is_not_left_in_the_cache(self):
        run, _ = fake_curl(fail_on="stripped")
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(survey.subprocess, "run", run), \
                    self.assertRaises(subprocess.TimeoutExpired):
                survey.download(d)
            self.assertEqual(sorted(os.listdir(d)), ["names.gz"])

    def test_the_next_run_fetches_what_the_interrupted_one_did_not(self):
        with tempfile.TemporaryDirectory() as d:
            run, _ = fake_curl(fail_on="stripped")
            with mock.patch.object(survey.subprocess, "run", run), \
                    self.assertRaises(subprocess.TimeoutExpired):
                survey.download(d)
            run, calls = fake_curl()
            with mock.patch.object(survey.subprocess, "run", run):
                paths = survey.download(d)
        self.assertEqual(calls, [survey.BULK["stripped"]])
        self.assertEqual(sorted(paths), ["names", "stripped"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
