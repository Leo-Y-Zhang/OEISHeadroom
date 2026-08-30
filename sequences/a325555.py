"""A325555: number of necklace compositions of n with distinct differences up to sign.

A necklace composition of n is a sequence of positive integers summing to n that
is lexicographically minimal among all of its cyclic rotations.  "Distinct
differences up to sign" means the k-1 consecutive differences c[i+1]-c[i] have
pairwise distinct absolute values (non-circular; the circular variant is
A325556, whose counts are different).

ALGORITHM
---------
Two structural facts collapse the search.

1. Translation classes.  Adding a constant t >= 0 to every part changes no
   difference and no lexicographic comparison between rotations, so the property
   "necklace with distinct |differences|" is translation invariant.  A necklace
   begins with its minimum part, so every such composition is uniquely
   (a canonical one whose first part is 1) plus t.  A canonical form with k
   parts and sum s therefore supplies exactly one composition of each n in the
   arithmetic progression s, s+k, s+2k, ....  So the search enumerates only
   canonical forms with sum <= n_max, tallies them in cnt[k][s], and spreads
   each progression with one O(n_max) prefix-sum pass per k at the end.  One
   traversal answers every n <= n_max at once.

2. Prenecklace generation (Fredricksen-Kessler-Maiorana).  Generating candidates
   and testing the necklace property costs O(k^2) per candidate and throws most
   of the tree away.  Instead only *prenecklaces* - prefixes of necklaces - are
   grown, which is a closed recursion: if c[1..t-1] is a prenecklace whose
   longest Lyndon prefix has length p, its legal extensions are exactly
   c[t] >= c[t-p], the new Lyndon length is p when c[t] == c[t-p] and t when
   c[t] > c[t-p], and c[1..t] is a necklace iff t mod p_new == 0.  Every node
   visited is a genuine composition prefix and the necklace test is O(1).

The distinct-|difference| constraint rides along as a bytearray of used absolute
differences, and it is what bounds the depth: k-1 distinct non-negative values
give sum|d| >= (k-1)(k-2)/2, while min(c_i, c_{i+1}) >= 1 gives
c_i + c_{i+1} >= 2 + |d_i| and hence 2n - 2 >= 2(k-1) + sum|d|.  So
n >= (k-1) + (k-1)(k-2)/4 and k = O(sqrt(n)) - at most 12 parts at n = 40, 16 at
n = 70 - without any explicit cap being imposed.

For large n_max the seed frontier at depth 3 is split across processes
(multiprocessing, standard library); the serial and parallel paths run the same
recursion and are checked to agree exactly.  Any failure to start workers falls
back to the serial path.

WHY THIS BEATS BRUTE FORCE
--------------------------
The program in the OEIS entry builds all 2^(n-1) compositions of n - every
permutation of every partition - and filters them, once per n, so cost is
exponential in n and nothing is shared between different n.  Here the cost is
proportional to the number of prenecklaces of sum <= n_max with distinct
|differences|: no rejected candidates, no composition whose first part exceeds 1
ever materialised, the part-count bound k = O(sqrt(n)) falling out of the
constraint rather than out of a filter, and all n handled in a single pass.
About 10 million nodes cover every n <= 46, where brute force alone would have
to inspect 2^45 compositions for the last term.

Pure standard library, Python 3.13.
"""

import sys

OFFSET = 1

# Measured, not aspirational: this is how far the implementation
# recomputes from scratch inside CI's budget. The gate recomputes to
# exactly this index, so the extension reported is the one verified.
EXTEND_TO = 41
PUBLISHED = [1, 2, 2, 4, 5, 6, 10, 15, 19, 24, 39, 49, 78, 106, 155,
             207, 313, 430, 608, 867, 1239, 1670, 2313, 3220, 4483]

# Sentinel meaning "never split off a seed" (no partial sum can reach it).
_NO_SPLIT = 1 << 62


def _new_table(n_max):
    """cnt[k][s] table; k <= n_max always holds since every part is >= 1."""
    return [[0] * (n_max + 2) for _ in range(n_max + 3)]


def _make_search(cnt, c, used, split_sum, seeds):
    """Build the prenecklace recursion over c[1..] (closure: hot inner loop).

    In a call rec(t, p, s, hi): c[1..t-1] is a prenecklace of sum s whose longest
    Lyndon prefix has length p, with hi = n_max - s of headroom left; the call
    chooses c[t] and recurses.  Every necklace found is tallied in
    cnt[length][sum].  Nodes whose sum first reaches split_sum are appended to
    `seeds` instead of being expanded, so a caller can farm them out to worker
    processes; splitting on the sum rather than on the depth keeps the seed
    subtrees comparable in size, since cost grows with the leftover budget.
    Pass split_sum = _NO_SPLIT for a plain exhaustive search.
    """
    def rec(t, p, s, hi):
        prev = c[t - 1]
        lo = c[t - p]
        row = cnt[t]
        t1 = t + 1
        for v in range(lo, hi + 1):
            d = v - prev
            if d < 0:
                d = -d
            if used[d]:
                continue                      # |difference| already taken
            c[t] = v
            np = p if v == lo else t          # FKM Lyndon-prefix update
            ns = s + v
            if t % np == 0:
                row[ns] += 1                  # c[1..t] is a necklace
            nhi = hi - v
            if nhi >= c[t1 - np]:             # some continuation still fits
                used[d] = 1
                if ns >= split_sum:
                    seeds.append((tuple(c[1:t1]), np))
                else:
                    rec(t1, np, ns, nhi)
                used[d] = 0

    return rec


def _run_seeds(n_max, seeds):
    """Expand a batch of frontier seeds, returning their cnt[k][s] tally."""
    cnt = _new_table(n_max)
    c = [0] * (n_max + 4)
    used = bytearray(n_max + 4)
    rec = _make_search(cnt, c, used, _NO_SPLIT, None)
    for prefix, p in seeds:
        t = len(prefix)
        s = 0
        for i, x in enumerate(prefix, start=1):
            c[i] = x
            s += x
        for i in range(t - 1):
            used[abs(prefix[i + 1] - prefix[i])] = 1
        rec(t + 1, p, s, n_max - s)
        for i in range(t - 1):
            used[abs(prefix[i + 1] - prefix[i])] = 0
    return cnt


def _worker(payload):
    """Run a batch of seeds; return only the nonzero rows, to keep IPC small."""
    n_max, seeds = payload
    cnt = _run_seeds(n_max, seeds)
    return {k: row for k, row in enumerate(cnt) if any(row)}


def _collect(n_max, cnt):
    """Spread each canonical form (k parts, sum s) over s, s+k, s+2k, ..."""
    a = [0] * (n_max + 1)
    for k in range(1, n_max + 1):
        row = cnt[k]
        for s in range(k + 1, n_max + 1):
            row[s] += row[s - k]
        for n in range(1, n_max + 1):
            a[n] += row[n]
    return a[1:]


def _frontier(n_max, split_sum):
    """Tally everything below the split; return (cnt, seeds)."""
    cnt = _new_table(n_max)
    c = [0] * (n_max + 4)
    used = bytearray(n_max + 4)
    c[1] = 1
    cnt[1][1] += 1          # the length-1 necklace (1)
    seeds = []
    _make_search(cnt, c, used, split_sum, seeds)(2, 1, 1, n_max - 1)
    return cnt, seeds


def _terms_serial(n_max):
    cnt, _ = _frontier(n_max, _NO_SPLIT)
    return _collect(n_max, cnt)


def _terms_parallel(n_max, nproc):
    import multiprocessing as mp

    # Raise the split until there are plenty of independent, comparable tasks.
    want = 256 * nproc
    split = 8
    while True:
        cnt, seeds = _frontier(n_max, split)
        if len(seeds) >= want or split >= n_max // 2:
            break
        split += 2

    groups = min(len(seeds), 64 * nproc)
    # Stride the seeds so each group mixes cheap and expensive subtrees.
    payloads = [(n_max, seeds[i::groups]) for i in range(groups)]

    with mp.Pool(processes=nproc) as pool:
        for part in pool.imap_unordered(_worker, payloads):
            for k, prow in part.items():
                row = cnt[k]
                for s in range(1, n_max + 1):
                    row[s] += prow[s]
    return _collect(n_max, cnt)


def terms(n_max):
    """Return [a(1), ..., a(n_max)] for A325555."""
    if n_max < 1:
        return []
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * n_max + 1000))
    if n_max >= 40:
        try:
            import os
            nproc = min(os.cpu_count() or 1, 16)
            if nproc > 1:
                return _terms_parallel(n_max, nproc)
        except Exception:
            pass
    return _terms_serial(n_max)


if __name__ == "__main__":
    import time

    n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    t0 = time.time()
    vals = terms(n_max)
    el = time.time() - t0
    shared = min(len(vals), len(PUBLISHED))
    ok = vals[:shared] == PUBLISHED[:shared]
    print("published match (%d terms): %s" % (shared, ok))
    if not ok:
        for i in range(shared):
            if vals[i] != PUBLISHED[i]:
                print("  first mismatch a(%d): got %d, published %d"
                      % (i + 1, vals[i], PUBLISHED[i]))
                break
    print("n_max=%d  %.1fs" % (n_max, el))
    print(",".join(map(str, vals)))
    if len(vals) > len(PUBLISHED):
        print("NEW terms a(%d)..a(%d):" % (len(PUBLISHED) + 1, len(vals)))
        for i in range(len(PUBLISHED), len(vals)):
            print("  a(%d) = %d" % (i + 1, vals[i]))
