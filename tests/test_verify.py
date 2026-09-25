"""Tests for the gate.

The gate's job is to refuse a claim, so most of these check that it refuses.
A verifier that has only ever been observed passing is not evidence of anything
- it is indistinguishable from a verifier wired to `return True`. Every failure
mode below is one that would otherwise let a wrong extension into the
repository looking exactly like a right one.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oeisheadroom.verify import check_one  # noqa: E402

PUBLISHED = [1, 2, 3, 5, 8, 13]
SNAPSHOT = {"A000001": {"data": PUBLISHED, "n_terms": len(PUBLISHED)}}


def write_module(tmpdir: str, body: str, name: str = "a000001.py") -> str:
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


HONEST = """
OFFSET = 1
PUBLISHED = [1, 2, 3, 5, 8, 13]
def terms(n_max):
    out = [1, 2, 3, 5, 8, 13, 21, 34]
    return out[:n_max]
"""


class TestAccepts(unittest.TestCase):
    def test_correct_module_passes_and_reports_the_extension(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, HONEST), SNAPSHOT, extend_to=8)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.n_published, 6)
        self.assertEqual(r.new_terms, [21, 34])

    def test_reproducing_without_extending_is_a_pass_with_nothing_new(self):
        """Correct and adds nothing is a legitimate outcome, not a failure."""
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, HONEST), SNAPSHOT, extend_to=6)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.new_terms, [])


class TestRefuses(unittest.TestCase):
    def test_one_wrong_term_fails_and_names_the_index(self):
        wrong = HONEST.replace("out = [1, 2, 3, 5, 8, 13,",
                               "out = [1, 2, 3, 5, 9, 13,")
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, wrong), SNAPSHOT, extend_to=8)
        self.assertFalse(r.ok)
        self.assertIn("a(5)", r.reason)      # offset 1, so index 4 is a(5)
        self.assertEqual(r.new_terms, [])

    def test_editing_published_to_match_a_wrong_output_still_fails(self):
        """The attack the snapshot exists to stop.

        A module that computes the wrong thing can be made self-consistent by
        editing its own PUBLISHED list. It then reproduces "its" published data
        perfectly. Only the independent snapshot catches it.
        """
        forged = """
OFFSET = 1
PUBLISHED = [1, 2, 3, 5, 9, 13]
def terms(n_max):
    return [1, 2, 3, 5, 9, 13, 22][:n_max]
"""
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, forged), SNAPSHOT, extend_to=7)
        self.assertFalse(r.ok)
        self.assertIn("disagrees with the OEIS snapshot", r.reason)

    def test_missing_snapshot_fails_rather_than_skipping(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, HONEST), {}, extend_to=8)
        self.assertFalse(r.ok)
        self.assertIn("no snapshot", r.reason)

    def test_a_module_that_raises_fails(self):
        boom = """
OFFSET = 1
PUBLISHED = [1, 2, 3, 5, 8, 13]
def terms(n_max):
    raise RuntimeError("ran out of memory")
"""
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, boom), SNAPSHOT, extend_to=8)
        self.assertFalse(r.ok)
        self.assertIn("raised", r.reason)

    def test_a_module_that_will_not_import_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, "def terms(:\n"), SNAPSHOT)
        self.assertFalse(r.ok)
        self.assertIn("will not load", r.reason)

    def test_returning_too_few_terms_fails(self):
        short = """
OFFSET = 1
PUBLISHED = [1, 2, 3, 5, 8, 13]
def terms(n_max):
    return [1, 2, 3]
"""
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, short), SNAPSHOT, extend_to=8)
        self.assertFalse(r.ok)
        self.assertIn("fewer than", r.reason)

    def test_empty_published_fails(self):
        empty = "OFFSET = 1\nPUBLISHED = []\ndef terms(n_max):\n    return []\n"
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, empty), SNAPSHOT)
        self.assertFalse(r.ok)
        self.assertIn("no published terms", r.reason)

    def test_an_edit_is_graded_even_when_size_and_mtime_are_unchanged(self):
        """The gate grades the file on disk, not a cached compilation of an
        earlier version of it. Python's bytecode cache accepts a .pyc whose
        recorded source size and whole-second mtime match, so a same-length
        edit inside the same second -- one digit swapped by a mutation tool,
        say -- would otherwise run the old code and pass."""
        stamp = (1_000_000_000, 1_000_000_000)
        with tempfile.TemporaryDirectory() as d:
            path = write_module(d, HONEST)
            os.utime(path, stamp)
            self.assertTrue(check_one(path, SNAPSHOT, extend_to=8).ok)
            write_module(d, HONEST.replace("8, 13, 21", "9, 13, 21"))
            os.utime(path, stamp)
            r = check_one(path, SNAPSHOT, extend_to=8)
        self.assertFalse(r.ok)
        self.assertIn("a(5)", r.reason)



class TestDeclaredExtension(unittest.TestCase):
    """EXTEND_TO must make the gate RECOMPUTE the extension, not trust it."""

    DECLARING = """
OFFSET = 1
EXTEND_TO = 8
PUBLISHED = [1, 2, 3, 5, 8, 13]
def terms(n_max):
    return [1, 2, 3, 5, 8, 13, 21, 34][:n_max]
"""

    def test_extend_to_is_honoured_without_being_passed_in(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, self.DECLARING), SNAPSHOT)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.new_terms, [21, 34])

    def test_a_module_claiming_further_than_it_computes_fails(self):
        """Declaring EXTEND_TO = 8 while only returning 6 terms is a lie the
        gate has to catch, not round down to a pass."""
        liar = self.DECLARING.replace("return [1, 2, 3, 5, 8, 13, 21, 34]",
                                      "return [1, 2, 3, 5, 8, 13]")
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, liar), SNAPSHOT)
        self.assertFalse(r.ok)
        self.assertIn("returned 6", r.reason)

    def test_an_explicit_argument_overrides_the_declaration(self):
        with tempfile.TemporaryDirectory() as d:
            r = check_one(write_module(d, self.DECLARING), SNAPSHOT, extend_to=7)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.new_terms, [21])

if __name__ == "__main__":
    unittest.main(verbosity=2)
