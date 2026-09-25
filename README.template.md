# OEISHeadroom

Find the OEIS sequences that stopped early because somebody's brute force ran
out of patience, then finish the job.

The OEIS marks sequences whose author wants more terms with the keyword `more`.
There are 26,751 of them, and almost none are attackable: probable-prime
searches are a specialist sport, and the famous short sequences are short
because supercomputers have already failed at them. This finds the residue --
**{{N_SURVEY}} counting sequences** whose published data stops at a value small
enough that the wall was patience, not difficulty -- and then attacks some.

## Results

**{{N_VERIFIED}} of {{N_ATTACKED}} implementations reproduce every term the OEIS
publishes** ({{N_PUBLISHED_CHECKED}} published values recomputed from scratch).
{{N_EXTENDED}} sequences were extended, by **{{N_NEW_TERMS}} new terms** in total.

{{RESULTS_TABLE}}

The `published` column is the OEIS data as of {{SNAPSHOT_DATE}}, before any of
this was submitted, and it stays there. All {{N_NEW_TERMS}} new terms have since
been accepted into the OEIS, so re-snapshotting now would quietly fold this
repository's own output into the data it is checked against -- {{N_PUBLISHED_CHECKED}}
independent values would become {{N_PUBLISHED_CHECKED}} plus {{N_NEW_TERMS}} of
its own, and the gate would be grading its own homework while still printing a
pass. The baseline is frozen and `snapshot` refuses to overwrite it without
`--force`.

### The new terms

{{NEW_TERMS}}

## Why you should believe any of this

You shouldn't, on my say-so. Run it:

```
pip install -e .
oeisheadroom verify          # recompute every published term, then go past them
oeisheadroom verify --live   # and check the OEIS publishes what was computed
oeisheadroom bfile           # render b-files for uploading, from verified terms
```

The argument is narrow and mechanical. **An extension is worth nothing unless
the same program also reproduces every term the OEIS already publishes.**
Agreeing with twenty-five published values by accident is not possible, so exact
agreement is evidence the definition was understood, and disagreement on one
value is proof it was not. `verify` does that first and refuses to report
anything past the published data until it passes.

Three properties of the gate are deliberate:

- **Default-deny.** A module that fails to import, whose `terms()` raises, or
  that has no snapshot is a FAILURE, never a skip. An unrunnable check and a
  passing check must not look alike.
- **The published data is snapshotted independently.** A wrong implementation
  can be made self-consistent by quietly editing its own idea of what OEIS says.
  `published.json` is fetched from OEIS and committed, and the module is checked
  against *it*, not against itself. There is a test for exactly this attack.
- **CI proves the gate goes red.** It corrupts one computed term and requires
  the same command to reject it. A gate never observed failing is decoration.

## Confirming the published record

The gate asks whether this repository is right. Since the extensions were
accepted there is a second question it cannot answer from the inside: whether
what the OEIS publishes is what was computed. An editor trimming a term, a
b-file pasted a line off, a submission assembled from an older run -- each puts
a wrong value into the OEIS under a human author's name, and leaves this
repository passing its own gate.

`oeisheadroom verify --live` fetches each entry's DATA field and its b-file and
compares both against the frozen baseline plus the terms the gate just
recomputed. Both, because an extension longer than the DATA field is published
in the b-file, so a check of DATA alone would confirm the head of it and never
see the rest; and because only the b-file states its indices, which can be
wrong on their own. Both have to pass. Every way either can disagree gets its
own verdict, because a check that reports "not approved yet" and "the published
value disagrees with mine" as the same yellow warning trains its reader to
ignore both:

| verdict | meaning |
|---|---|
| `CONFIRMED` | OEIS carries some or all of these terms, every one equal |
| `AHEAD` | all of them, and more past them: somebody extended further |
| `PENDING` | still only the baseline, nothing from here is live yet |
| `MISMATCH` | OEIS and this repository disagree on a term past the baseline |
| `REVISED` | OEIS changed a term, or the offset, the gate verified against |
| `UNREACHABLE` | could not fetch or read -- not confirmed, which is not a pass |

The first three are fine; the last three exit non-zero. CI runs this weekly
rather than on every push: wiring a network check into the gate is how a gate
stops running the day the network does.

`oeisheadroom bfile` renders the OEIS b-file for each sequence -- `n a(n)` per
line -- from the terms the gate just recomputed, never from a stored list, since
a b-file typed up from an old run is exactly the transcription error above. It
also reports which extensions overflow the DATA field (about 260 characters) and
therefore need a b-file rather than merely allowing one.

## Finding the sequences

```
oeisheadroom survey
```

Two things had to be got right here, and both were got wrong first. They are
worth recording because each produced a confident, useless answer.

**The search API cannot do this.** It caps pagination at `start=200`, so it will
not enumerate a 19,113-result query however politely you ask. The bulk dumps
(`names.gz`, `stripped.gz`) carry all 399,277 sequences and filter offline with
complete coverage.

**Few terms means HARD, not neglected -- unless the terms are also small.** The
first filter keyed on term count alone and returned Dedekind numbers, posets and
polycubes: every one famous, every one hopeless, all short because the answers
explode. What separates neglect from difficulty is *the magnitude of the last
published term*. A counting sequence that stops after twelve terms at a value of
forty thousand did not stop because the answer got big.

**And that inference only holds if the sequence grows.** Counts of maximum-size
objects oscillate violently -- A375299, longest winning paths in n X n Hex, runs
`... 1298, 83648, 16631833, 70630` -- so the last term there measures nothing at
all. That was checked against the authoritative `%S`/`%T` lines before the
filter was changed: the data is real, the assumption was wrong. Monotonicity is
a criterion, not a preference. Both mistakes have tests named after them.

## What this does not claim

**This repository is not the OEIS.** The terms are computed, verified against
the published data, and published here for anyone to check. Submitting them was
a separate act by a human author: all seven extensions were submitted and
reviewed by OEIS editors, and all seven are now published there (the last,
A337114 a(25)-a(36), on 2 September 2026). The OEIS entries are the record;
this repository is the evidence behind them.

A verified extension is a claim about *a program agreeing with the OEIS on every
value the OEIS states, and continuing*. It is not a proof. An independent
implementation would be better evidence, and for anything that matters, two
would be better than one.

Where an implementation failed to reproduce the published terms, that is
reported as a failure in the table above rather than removed. A repository whose
premise is that green results need checking should show its own red ones.

## Layout

| path | purpose |
|---|---|
| `oeisheadroom/survey.py` | the filter over all 399,277 sequences |
| `oeisheadroom/verify.py` | the gate: reproduce, then extend |
| `oeisheadroom/__main__.py` | CLI |
| `sequences/aNNNNNN.py` | one independent implementation per sequence |
| `published.json` | what OEIS published, with the date it was fetched |
| `survey.json` | the {{N_SURVEY}} sequences with headroom |
| `tests/` | the gate's own tests, mostly cases it must refuse |

`README.md` is generated by `make_readme.py` from the verifier's real output and
fails on any unfilled placeholder, so no number in it is hand-typed.

## Licence

Proprietary source-available -- see [LICENSE](LICENSE). You may read it, run it,
and publish what you find, including a refutation.
