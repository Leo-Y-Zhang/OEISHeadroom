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

import contextlib
import http.server
import io
import os
import shutil
import subprocess
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oeisheadroom import verify  # noqa: E402
from oeisheadroom.verify import (  # noqa: E402
    Result,
    bfile_text,
    confirm_bfile,
    confirm_live,
    confirm_one,
    data_line,
    fetch_bfile,
    fetch_published,
    fits_in_data,
    is_synthesized,
    parse_bfile,
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


def table(terms, offset=1, first_index=None, synthesized=False):
    """A b-file as the OEIS serves it: an uploaded one by default, or with the
    header the OEIS writes on one it synthesized from the DATA field."""
    start = offset if first_index is None else first_index
    head = ("# A000001 (b-file synthesized from sequence entry)\n" if synthesized
            else "# A000001: Table of n, a(n) for n = 1..8.\n")
    return head + "".join(f"{start + i} {t}\n" for i, t in enumerate(terms))


class TestParseBfile(unittest.TestCase):
    def test_reads_index_value_pairs_and_skips_comments_and_blanks(self):
        text = "# header\n\n1 1\n2 -3\r\n  3   123456789012345678901234567890  \n"
        self.assertEqual(parse_bfile(text),
                         [(1, 1), (2, -3), (3, 123456789012345678901234567890)])

    def test_a_line_that_is_not_n_and_a_n_is_an_error_not_a_skip(self):
        """Skipping it would read a damaged b-file as a shorter, intact one."""
        for bad in ("1 1\n2 2 2\n", "1 1\n2 x\n", "<!DOCTYPE html>\n", "1 1\n2\n"):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                parse_bfile(bad)

    def test_a_b_file_with_no_terms_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_bfile("# nothing here\n")

    def test_a_synthesized_b_file_is_recognised_by_its_header(self):
        self.assertTrue(is_synthesized(table(BASE, synthesized=True)))
        self.assertFalse(is_synthesized(table(BASE)))


class TestConfirmBfile(unittest.TestCase):
    def check(self, text, offset=1):
        return confirm_bfile("A000001", offset, BASE, OURS, text)

    def test_a_b_file_carrying_all_our_terms_is_confirmed(self):
        r = self.check(table(BASE + OURS))
        self.assertEqual(r.status, "CONFIRMED")
        self.assertEqual(r.n_confirmed, 3)

    def test_a_b_file_pasted_a_line_off_is_a_mismatch(self):
        """The case the README names: every value one row early."""
        r = self.check(table(BASE + OURS[1:] + [55]))
        self.assertEqual(r.status, "MISMATCH")
        self.assertIn("a(6)", r.detail)

    def test_a_skipped_index_past_the_baseline_is_a_mismatch(self):
        text = table(BASE + OURS).replace("7 21\n", "")
        r = self.check(text)
        self.assertEqual(r.status, "MISMATCH")
        self.assertIn("a(8)", r.detail)

    def test_a_skipped_index_inside_the_baseline_is_revised(self):
        r = self.check(table(BASE + OURS).replace("3 3\n", ""))
        self.assertEqual(r.status, "REVISED")

    def test_a_changed_baseline_value_is_revised(self):
        r = self.check(table([1, 2, 4, 5, 8] + OURS))
        self.assertEqual(r.status, "REVISED")
        self.assertIn("a(3)", r.detail)

    def test_a_b_file_starting_at_another_offset_is_revised(self):
        """The DATA field carries no indices, so only the b-file can show that
        the OEIS moved the offset every a(n) here is numbered from."""
        r = self.check(table(BASE + OURS, first_index=0))
        self.assertEqual(r.status, "REVISED")
        self.assertIn("starts at a(0)", r.detail)

    def test_an_unreadable_b_file_is_not_confirmed(self):
        r = self.check("<html><body>Please try again later</body></html>\n")
        self.assertEqual(r.status, "UNREACHABLE")
        self.assertFalse(r.ok)

    def test_an_unfetchable_b_file_is_not_confirmed(self):
        r = self.check(None)
        self.assertEqual(r.status, "UNREACHABLE")
        self.assertFalse(r.ok)


class TestConfirmLive(unittest.TestCase):
    def snapshot(self):
        return {"A000001": {"data": BASE, "n_terms": len(BASE)}}

    def result(self, ok=True):
        return Result("A000001", ok, "reproduces every published term",
                      len(BASE), len(BASE) + len(OURS), list(OURS), 0.0, 1)

    def run_live(self, data, bfile):
        return confirm_live([self.result()], self.snapshot(),
                            fetch=lambda sid: data, fetch_b=lambda sid: bfile,
                            pause=0)

    def test_fetches_and_classifies_each_passing_sequence(self):
        out = self.run_live(BASE + OURS, table(BASE + OURS))
        self.assertEqual([r.status for r in out], ["CONFIRMED"])

    def test_a_wrong_term_past_the_data_field_is_caught_in_the_b_file(self):
        """An extension too long for DATA is published in its b-file, so a
        check reading DATA alone confirms the head and never sees the rest."""
        out = self.run_live(BASE + OURS[:1], table(BASE + [13, 21, 35]))
        self.assertEqual(out[0].status, "MISMATCH")
        self.assertIn("b-file", out[0].detail)
        self.assertIn("a(8)", out[0].detail)

    def test_the_b_file_speaks_for_terms_the_data_field_was_trimmed_of(self):
        out = self.run_live(BASE + OURS[:1], table(BASE + OURS))
        self.assertEqual(out[0].status, "CONFIRMED")
        self.assertEqual(out[0].n_confirmed, 3)

    def test_a_wrong_data_field_is_not_rescued_by_a_right_b_file(self):
        out = self.run_live(BASE + [13, 22], table(BASE + OURS))
        self.assertEqual(out[0].status, "MISMATCH")
        self.assertIn("DATA", out[0].detail)

    def test_an_unfetchable_b_file_is_not_confirmed_by_the_data_field(self):
        """Default-deny: half the published record checked is not a pass."""
        out = self.run_live(BASE + OURS, None)
        self.assertEqual(out[0].status, "UNREACHABLE")

    def test_a_mismatch_outranks_an_unreachable_source(self):
        out = self.run_live(None, table(BASE + [13, 21, 35]))
        self.assertEqual(out[0].status, "MISMATCH")

    def test_when_both_fail_both_reasons_are_given(self):
        out = self.run_live(None, "<html>challenge</html>\n")
        self.assertEqual(out[0].status, "UNREACHABLE")
        self.assertIn("DATA: could not fetch", out[0].detail)
        self.assertIn("b-file: could not read", out[0].detail)

    def test_a_synthesized_b_file_checks_the_data_field_without_fetching_it(self):
        """The OEIS rendered it from DATA, so it is DATA with indices. And the
        endpoint DATA comes from answers automated clients with a challenge."""
        calls = []

        def fetch(sid):
            calls.append(sid)
            return None

        out = confirm_live([self.result()], self.snapshot(), fetch=fetch,
                           fetch_b=lambda sid: table(BASE + OURS, synthesized=True),
                           pause=0)
        self.assertEqual(out[0].status, "CONFIRMED")
        self.assertEqual(out[0].n_confirmed, 3)
        self.assertIn("synthesized", out[0].detail)
        self.assertEqual(calls, [])

    def test_a_wrong_term_in_a_synthesized_b_file_is_a_mismatch(self):
        out = self.run_live(None, table(BASE + [13, 21, 35], synthesized=True))
        self.assertEqual(out[0].status, "MISMATCH")
        self.assertIn("a(8)", out[0].detail)

    def test_an_uploaded_b_file_does_not_stand_in_for_the_data_field(self):
        """An uploaded b-file is a separate record from DATA; if DATA cannot
        be fetched, half the published record is unchecked, which is not a
        pass."""
        out = self.run_live(None, table(BASE + OURS))
        self.assertEqual(out[0].status, "UNREACHABLE")
        self.assertIn("DATA", out[0].detail)

    def test_a_sequence_that_failed_the_gate_is_not_reported_twice(self):
        calls = []

        def fetch(sid):
            calls.append(sid)
            return BASE

        out = confirm_live([self.result(ok=False)], self.snapshot(),
                           fetch=fetch, fetch_b=fetch, pause=0)
        self.assertEqual(out, [])
        self.assertEqual(calls, [])           # and it does not hit the network


@contextlib.contextmanager
def served(body: bytes, returncode: int = 0, stderr: bytes = b"", log=None):
    """Stand in for curl: every fetch returns this body, exit status and stderr.
    What the fetch reports on stderr goes to `log` (a StringIO), or nowhere."""
    done = subprocess.CompletedProcess([], returncode, stdout=body, stderr=stderr)
    with mock.patch.object(verify.subprocess, "run", return_value=done) as run, \
            contextlib.redirect_stderr(log if log is not None else io.StringIO()):
        yield run


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

    def test_says_why_a_fetch_failed(self):
        """UNREACHABLE alone does not say whether to retry, change the client
        or ask the OEIS. The reason goes to stderr, and so into the CI log."""
        log = io.StringIO()
        with served(b"", returncode=22, log=log,
                    stderr=b"curl: (22) The requested URL returned error: 403"):
            fetch_published("A000001")
        self.assertIn("id:A000001", log.getvalue())
        self.assertIn("error: 403", log.getvalue())

    def test_quotes_a_page_that_is_not_json(self):
        log = io.StringIO()
        with served(b"<html><title>Checking your browser</title>", log=log):
            fetch_published("A000001")
        self.assertIn("not JSON", log.getvalue())
        self.assertIn("Checking your browser", log.getvalue())


class TestFetchBfile(unittest.TestCase):
    def test_asks_for_the_entry_s_own_b_file(self):
        with served(b"1 1\n") as run:
            self.assertEqual(fetch_bfile("A319381"), "1 1\n")
        self.assertIn("https://oeis.org/A319381/b319381.txt", run.call_args.args[0])

    def test_an_http_error_is_none_rather_than_the_error_page(self):
        with served(b"<html>404</html>", returncode=22):
            self.assertIsNone(fetch_bfile("A000001"))

    def test_a_byte_order_mark_is_not_part_of_the_first_line(self):
        with served(b"\xef\xbb\xbf1 1\n"):
            self.assertEqual(fetch_bfile("A000001"), "1 1\n")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "/b000001.txt")
            self.end_headers()
        elif self.path == "/b000001.txt":
            body = b"1 1\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


class TestGetOverHttp(unittest.TestCase):
    """The fetch through a real curl and a local server, since the flags are
    the behaviour: an error status must be a failed fetch, not an error page
    handed on as content, and a redirect must be followed."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("curl"):
            raise unittest.SkipTest("curl is not installed")
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.no_proxy = mock.patch.dict(os.environ, {"NO_PROXY": "*", "no_proxy": "*"})
        cls.no_proxy.start()

    @classmethod
    def tearDownClass(cls):
        cls.no_proxy.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_the_body_is_returned(self):
        self.assertEqual(verify._get(self.base + "/b000001.txt", 10), b"1 1\n")

    def test_a_redirect_is_followed(self):
        self.assertEqual(verify._get(self.base + "/moved", 10), b"1 1\n")

    def test_an_error_status_is_none_and_says_which(self):
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            self.assertIsNone(verify._get(self.base + "/missing", 10))
        self.assertIn("404", log.getvalue())


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

    def test_the_cap_itself_still_fits(self):
        self.assertTrue(fits_in_data([10 ** (verify.DATA_CAP - 1)]))
        self.assertFalse(fits_in_data([10 ** verify.DATA_CAP]))


if __name__ == "__main__":
    unittest.main()
