"""Independent tiny enumerations and exact checks of packed combinatorial states."""

from collections import Counter
from functools import lru_cache
from itertools import groupby
from pathlib import Path

import pytest

from oeisheadroom.verify import load_module

SEQUENCES = Path(__file__).resolve().parents[1] / "sequences"
a319381, a323586, a325555, a325556, a337114, a347414, a353403 = (
    load_module(str(SEQUENCES / f"a{number}.py"))
    for number in (319381, 323586, 325555, 325556, 337114, 347414, 353403))


def compositions(n):
    if n == 0:
        yield ()
    for first in range(1, n + 1):
        for rest in compositions(n - first):
            yield (first,) + rest


def necklace_counts(limit, circular):
    counts = []
    for n in range(1, limit + 1):
        count = 0
        for word in compositions(n):
            if word != min(word[i:] + word[:i] for i in range(len(word))):
                continue
            following = word[1:] + word[:1] if circular else word[1:]
            differences = [abs(a - b) for a, b in zip(word, following, strict=False)]
            count += len(differences) == len(set(differences))
        counts.append(count)
    return counts


def test_necklace_algorithms_against_all_small_compositions():
    assert a325555.terms(11) == necklace_counts(11, circular=False)
    assert a325556.terms(11, workers=1) == necklace_counts(11, circular=True)
    assert a325555.terms(0) == a325556.terms(0, workers=1) == []


@pytest.mark.parametrize("split", [2, 4, 7])
def test_necklace_seed_batches_preserve_used_differences_and_every_count(split):
    limit = 11
    table, seeds = a325555._frontier(limit, split)
    # Exercise worker serialization and resuming prefixes without processes.
    chunks = [a325555._worker((limit, seeds[i::3])) for i in range(3)]
    for chunk in chunks:
        for length, row in chunk.items():
            for weight, count in enumerate(row):
                table[length][weight] += count
    assert a325555._collect(limit, table) == necklace_counts(limit, circular=False)


def test_circular_shape_slices_include_boundary_first_values():
    # (0,0,1,3) and (0,0,3,1) have differences 0,1,2,3 in different orders.
    assert a325556._count_shapes(4, 4, first=0)[4] == 2
    for length in (3, 4, 5):
        budget = 9
        slices = [a325556._count_shapes(length, budget, first=i) for i in range(budget + 1)]
        total = [sum(values) for values in zip(*slices, strict=True)]
        assert total == a325556._count_shapes(length, budget)
    assert a325556._count_shapes(2, 4) == [0] * 5


def test_circular_parallel_failure_discards_partial_results(monkeypatch):
    class InterruptedPool:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def imap_unordered(self, worker, tasks, **kwargs):
            for task in tasks:
                part = worker(task)
                if any(part[1]):
                    yield part
                    raise OSError("worker stopped after a partial result")
            pytest.fail("fixture must produce a nonzero partial result")

    import multiprocessing

    monkeypatch.setattr(multiprocessing, "Pool", InterruptedPool)
    assert a325556.terms(11, workers=2) == necklace_counts(11, circular=True)


def partitions(n):
    return {tuple(sorted(word, reverse=True)) for word in compositions(n)}


def test_partitions_canonical_keys_and_subdiagrams():
    for n in range(8):
        actual = list(a323586._partitions(n))
        assert len(actual) == len(set(actual))
        assert set(actual) == partitions(n)
    assert a323586._canon((8, 6, 5, 4, 3), 4) == (4, 2, 1, 1)
    assert a323586._canon((8, 6), 0) == ()
    shape = (4, 2, 1)
    for cap in range(8):
        expected = {(p, size) for size in range(1, cap + 1) for p in partitions(size)
                    if len(p) <= len(shape) and all(a <= b for a, b in zip(p, shape, strict=False))}
        actual = a323586._subs(shape, cap)
        assert len(actual) == len(expected)
        assert set(actual) == expected


def test_plane_partition_chain_dp_against_untruncated_enumeration():
    def chains(previous, budget):
        if budget == 0:
            return 1
        count = 0
        for size in range(1, budget + 1):
            for row in partitions(size):
                if previous is None or (row != previous and len(row) <= len(previous)
                                        and all(a <= b for a, b in zip(row, previous, strict=False))):
                    count += chains(row, budget - size)
        return count

    assert a323586.terms(7) == [chains(None, n) for n in range(8)]
    assert a323586._F((1,), 0, 1) == 1
    assert a323586._F((1,), 1, 1) == 0  # repeated rows are forbidden


def test_plane_tree_chain_condition_against_all_ordered_trees():
    @lru_cache(None)
    def forests(n):
        if n == 0:
            return ((),)
        return tuple((tree,) + rest for size in range(1, n + 1)
                     for tree in forests(size - 1) for rest in forests(n - size))

    def valid(tree):
        return (all(valid(child) for child in tree)
                and all(b in a for a, b in zip(tree, tree[1:], strict=False)))

    expected = [sum(valid(tree) for tree in forests(n - 1)) for n in range(1, 10)]
    for n in range(10):
        # The last coefficient uses a separate correction in the packed DP.
        assert a319381.terms(n) == expected[:n]


@lru_cache(None)
def rooted_forests(n):
    if n == 0:
        return ((),)
    return tuple(sorted({tuple(sorted((tree,) + rest)) for size in range(1, n + 1)
                         for tree in rooted_forests(size - 1)
                         for rest in rooted_forests(n - size)}))


def forest_orbits(forest):
    parts = []
    for tree, copies in Counter(forest).items():
        parts.extend(copies * size for size in (1,) + forest_orbits(tree))
    return tuple(sorted(parts))


def unrooted_orbits(tree):
    edges = []

    def build(children, parent=None):
        vertex = len(edges)
        edges.append([])
        if parent is not None:
            edges[parent].append(vertex)
            edges[vertex].append(parent)
        for child in children:
            build(child, vertex)

    def rooted_code(vertex, parent=None):
        return tuple(sorted(rooted_code(child, vertex) for child in edges[vertex] if child != parent))

    build(tree)
    # Vertices are interchangeable exactly when rooting there gives isomorphic trees.
    classes = Counter(rooted_code(vertex) for vertex in range(len(edges)))
    return tuple(sorted(classes.values()))


def test_orbit_partition_algorithms_against_actual_small_forests_and_trees():
    forest_counts = [len({forest_orbits(f) for f in rooted_forests(n)}) for n in range(1, 9)]
    tree_counts = [len({unrooted_orbits(t) for t in rooted_forests(n - 1)}) for n in range(1, 9)]
    assert a347414.terms(8) == forest_counts
    assert a337114.terms(8) == tree_counts
    assert a347414.terms(0) == a337114.terms(0) == []


def test_orbit_partition_encoding_scales_parts_without_losing_multiplicity():
    bits = 4
    # Three singleton orbits and two orbits of size 5; digits contain multiplicities.
    code = (3 << bits) + (2 << (5 * bits))
    assert a347414._scale(code, 1, bits) == code
    assert a347414._scale(code, 3, bits) == (3 << (3 * bits)) + (2 << (15 * bits))
    assert a347414._scale(0, 3, bits) == 0


def test_usage_capacity_and_combinatorial_multiplicities():
    bits = 4
    one = 1 << bits
    assert set(a347414._usages(one, 1, 1, 3, bits)) == {
        (1, one, (1,)), (2, 1 << (2 * bits), (2,)), (3, 1 << (3 * bits), (3,)),
    }
    assert a347414._usages(one, 2, 0, 5, bits) == []
    assert a347414._usages(one, 2, 1, 1, bits) == []
    assert a347414._ways(2, (1, 1)) == 1
    assert a347414._ways(3, (2, 1)) == 6
    assert a347414._ways(3, (2, 2, 1)) == 3
    assert a347414._ways(1, (2, 1)) == 0
    assert a337114._partitions_at_most(4, 2) == [(4,), (3, 1), (2, 2)]
    assert a337114._partitions_at_most(0, 0) == [()]
    assert a337114._profiles(2, 2, 2) == [((1,), 2, 2), ((2,), 4, 2), ((1, 1), 4, 1)]
    assert a337114._profiles(1, 1, a337114.CAP + 1) == [((1,), 1, a337114.CAP)]


def run_reversal_count(n):
    count = 0
    for word in compositions(n):
        pattern = tuple(len(tuple(group)) for _, group in groupby(word))[::-1]
        # Enumerate selected positions; do not reuse the production greedy scan.
        count += any(tuple(value for i, value in enumerate(word) if mask & (1 << i)) == pattern
                     for mask in range(1 << len(word)))
    return count


def test_reversed_run_search_and_task_slices_against_subsequence_definition():
    expected = [run_reversal_count(n) for n in range(10)]
    assert a353403.terms(9, parallel=False) == expected
    assert a353403._count_serial(0) == 1
    assert a353403._count_serial(-1) == 0
    for depth in (1, 2, 3):
        _, shallow = a353403._tasks(9, depth)
        slices = [a353403._count_slice(9, depth, i, 3) for i in range(3)]
        assert shallow + sum(slices) == expected[9]
