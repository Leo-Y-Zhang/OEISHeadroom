# OEISHeadroom

Find the OEIS sequences that stopped early because somebody's brute force ran
out of patience, then finish the job.

The OEIS marks sequences whose author wants more terms with the keyword `more`.
There are 26,751 of them, and almost none are attackable: probable-prime
searches are a specialist sport, and the famous short sequences are short
because supercomputers have already failed at them. This finds the residue --
**1,765 counting sequences** whose published data stops at a value small
enough that the wall was patience, not difficulty -- and then attacks some.

## Results

**7 of 7 implementations reproduce every term the OEIS
publishes** (153 published values recomputed from scratch).
7 sequences were extended, by **123 new terms** in total.

| sequence | published | new | total | what it counts |
|---|---:|---:|---:|---|
| [A319381](https://oeis.org/A319381) | 22 | **+28** | 50 | Number of plane trees with n nodes where the sequence of branches directly... |
| [A323586](https://oeis.org/A323586) | 14 | **+27** | 41 | Number of plane partitions of n with no repeated rows (or, equivalently, n... |
| [A325556](https://oeis.org/A325556) | 25 | **+17** | 42 | Number of necklace compositions of n with distinct circular differences up... |
| [A325555](https://oeis.org/A325555) | 25 | **+16** | 41 | Number of necklace compositions of n with distinct differences up to sign. |
| [A347414](https://oeis.org/A347414) | 25 | **+13** | 38 | Number of partitions of n which occur as the automorphism orbit sizes of a... |
| [A337114](https://oeis.org/A337114) | 24 | **+12** | 36 | Number of distinct node-partitions of n-vertex trees. |
| [A353403](https://oeis.org/A353403) | 18 | **+10** | 28 | Number of compositions of n whose own reversed run-lengths are a subsequen... |

Published data snapshotted from OEIS on 2026-08-30.

### The new terms

**A319381** -- a(23)..a(50):

```
1390, 1873, 2494, 3323, 4376, 5830, 7655, 10091, 13281, 17363, 22633, 29610, 38419, 50029, 64812, 84032, 108529, 140325, 180808, 233007, 299489, 384898, 493435, 633090, 810069, 1036427, 1324168, 1690879
```

**A323586** -- a(14)..a(40):

```
1939, 3127, 4964, 7844, 12331, 19192, 29747, 45837, 70177, 106882, 162065, 244407, 366991, 548722, 816954, 1211346, 1789655, 2633781, 3862730, 5645935, 8224867, 11944079, 17292764, 24961488, 35928736, 51572110, 73827039
```

**A325555** -- a(26)..a(41):

```
6066, 8347, 11522, 15432, 21094, 28448, 38750, 52060, 70635, 93595, 127353, 169419, 227569, 301797, 406086, 537445
```

**A325556** -- a(26)..a(42):

```
2479, 3483, 4675, 6321, 8613, 11667, 15769, 21521, 28719, 38181, 51655, 67783, 90825, 119529, 158677, 206837, 273913
```

**A337114** -- a(25)..a(36):

```
1430, 1910, 2229, 2913, 3397, 4431, 5092, 6619, 7651, 9727, 11311, 14280
```

**A347414** -- a(26)..a(38):

```
2231, 2821, 3399, 4308, 5096, 6457, 7654, 9516, 11313, 14004, 16444, 20411, 23931
```

**A353403** -- a(18)..a(27):

```
4588, 8270, 14381, 25491, 45054, 79902, 141055, 249741, 442169, 783293
```


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
| `survey.json` | the 1,765 sequences with headroom |
| `tests/` | the gate's own tests, mostly cases it must refuse |

`README.md` is generated by `make_readme.py` from the verifier's real output and
fails on any unfilled placeholder, so no number in it is hand-typed.

## Licence

Proprietary source-available -- see [LICENSE](LICENSE). You may read it, run it,
and publish what you find, including a refutation.
