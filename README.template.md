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

Published data snapshotted from OEIS on {{SNAPSHOT_DATE}}.

### The new terms

{{NEW_TERMS}}

## Why you should believe any of this

You shouldn't, on my say-so. Run it:

```
pip install -e .
oeisheadroom verify          # recompute every published term, then go past them
oeisheadroom verify --live   # and re-check the published data against OEIS now
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

## Submitting these to the OEIS

[SUBMISSION.md](SUBMISSION.md) holds a copy-paste block per sequence: the DATA
line, the line to **append** to EXTENSIONS, and a short note for the submission
box. Regenerate it with `python make_submission.py` after any change to
`sequences/`.

Two traps it handles rather than leaves to the submitter. The DATA line is
truncated to the OEIS's ~260 character limit, because an overflowing one is
silently mangled by the form. And the EXTENSIONS field **accumulates** -- A337114
already credits Bert Dobbelaere for a(13)-a(24), so the pack prints the existing
lines with a keep-this warning, and the generator exits rather than claim a
sequence has no prior extensions when it cannot confirm that.

## What this does not claim

**Nothing here has been submitted to the OEIS.** The terms are computed,
verified against the published data, and published here for anyone to check.
Submitting them is a separate act requiring a human author, and the OEIS asks
for editorial correspondence to be written by the person submitting.

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
