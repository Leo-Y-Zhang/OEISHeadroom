# Mutation-guided unit tests

Added 50 pytest cases in four files. Production code is unchanged; no import
seams or runtime dependencies were needed. The existing CI test job now installs
pytest 8.4.2 and runs `pytest -q` in addition to its original checks.

The core checks are `check_one`, `check_all`, `confirm_one`, `confirm_bfile`,
`confirm_live`, the CLI exit statuses, and `bfile --check`. Tests exercise valid
inputs alongside changed values, missing rows, wrong indices/counts, and
truncation. Algorithm tests use small independent enumerations of compositions,
ordered trees, rooted forests, unrooted vertex orbits, and partition chains.
Worker splitting and interrupted-worker fallback are exercised without starting
worker processes in the new tests.

The mutation experiment tries 53 selected edits, individually, in temporary
copies. The complete source edits and measured outcomes are in
[mutation_results.json](mutation_results.json); the reproducible runner is
[mutation_check.py](mutation_check.py). This is a targeted experiment, not an
exhaustive mutation score.

“Before” means the original unittest suite plus the offline CI gate and its
deliberate-corruption probe. Tests run first; the gate runs only for survivors.
The original tests killed 13 mutants and the gate killed another 15. “After”
adds the new pytest tests: pytest alone killed all 53. There were no syntax-error
mutants or timeouts counted as kills.

| Module | Mutants tried | Killed before | Killed after |
|---|---:|---:|---:|
| `oeisheadroom/verify.py` | 16 | 13 | 16 |
| `oeisheadroom/__main__.py` | 6 | 1 | 6 |
| `oeisheadroom/survey.py` | 7 | 0 | 7 |
| `sequences/a319381.py` | 3 | 0 | 3 |
| `sequences/a323586.py` | 3 | 2 | 3 |
| `sequences/a325555.py` | 4 | 2 | 4 |
| `sequences/a325556.py` | 3 | 2 | 3 |
| `sequences/a337114.py` | 4 | 3 | 4 |
| `sequences/a347414.py` | 3 | 3 | 3 |
| `sequences/a353403.py` | 4 | 2 | 4 |
| **Total** | **53** | **28** | **53** |

Gate measurement caches the actual full-range `terms()` outputs, keyed by source
SHA256 and requested target. Only unchanged algorithm sources use that cache;
a mutated sequence algorithm is always recomputed. The real CLI, loader,
snapshot, length checks, value checks and exit-status checks still run. A second
invocation changes the first computed value, as CI does, and must exit nonzero.
It replays the values observed during the first invocation. This avoids running
unrelated expensive searches for every verifier mutation. The full uncached gate
and an actual source-file corruption/restoration probe were also run separately.

Each new test file kills previously surviving mutants:

| New test file | Example mutation killed and location |
|---|---|
| `test_cli_integrity.py` | C02: disable `if live_failed` in `cmd_verify`, accepting a live mismatch; C04: disable `have != text` in `cmd_bfile`, accepting corrupt exports; C06: omit newly computed terms from exports. |
| `test_verifier_boundaries.py` | V15: discard the per-sequence target lookup in `check_all`; V16: compare only `live[:n - 1]` with `baseline[:-1]` in `confirm_one`, accepting a changed last baseline value or a file one row short. |
| `test_survey_boundaries.py` | S01: change the inclusive minimum term-count comparison to strict; S04: change `growth > MAX_GROWTH` to `>=`, rejecting the valid limit; S07: negate the ID join condition in `load`. |
| `test_sequence_logic.py` | T03: subtract rather than add the last polynomial coefficient correction in `a319381.terms`; N04: forget used prefix differences in `a325555._run_seeds`; R03: skip the first assigned task in `a353403._count_slice`. |

The T03 error only changes the last computed term, which lies beyond the frozen
baseline during the normal gate run. Testing multiple small horizons against an
independent enumeration catches this wrong extension. The live-verifier and
export tests similarly check failures that an entirely valid offline fixture
cannot expose.

## Commands and results

Re-measured on a real checkout with Python 3.13 (the CI version) and pytest 8.4.2:

| Command | Result |
|---|---|
| `python tests/mutation_check.py before --output tests/mutation_results.json --cache .mutation-cache.json` | 28/53 killed by the original unittest suite and the offline gate with its corruption probe. |
| `python tests/mutation_check.py after --output tests/mutation_results.json --cache .mutation-cache.json` | 53/53 killed by pytest. |
| `python -m unittest discover -s tests` | OK |
| `pytest -q` | 140 passed in 1.01 s |
| `python -m oeisheadroom verify` | Exit 0: 7/7 sequences reproduce every published term; 123 new terms computed past them. |
| `ruff check .` | All checks passed |
| `git diff --check` | Clean |

No SAT solving or network requests occur in the new tests. Mutation coverage
outside the 53 selected edits remains unmeasured.
