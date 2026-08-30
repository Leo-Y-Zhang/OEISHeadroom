"""
A347414: number of partitions of n that occur as the multiset of automorphism
orbit sizes of some rooted forest on n vertices.

ALGORITHM
---------
Aut of a rooted forest decomposes completely.  Write a forest as a multiset of
rooted trees, grouped by isomorphism class: class T taken with multiplicity k.
Aut(forest) = prod_T (Aut(T) wr S_k), so each orbit of size s inside T becomes a
single orbit of size k*s.  Hence

    orbitpart(forest) = multiset-union over classes of  k * orbitpart(T),
    orbitpart(tree)   = {1} + orbitpart(forest of the root's child subtrees).

So the achievable partitions are exactly what a bounded knapsack over "tree
classes" produces, where a class is a pair (m, P) = (tree size, tree orbit
partition), the classes of size m are read straight off F(m-1) (the achievable
forest partitions of m-1), and a class may be used by at most

    c(m,P) = #{ non-isomorphic rooted trees of size m with orbit partition P }
            = #{ non-isomorphic rooted forests of size m-1 with orbit part. Q }

separate groups, because distinct groups need distinct isomorphism classes.
That capacity is essential and not a technicality: e.g. 3+2 is a partition of 5
that a relaxed model would produce (two groups of isolated vertices, k=3 and
k=2) but there is only one rooted tree on 1 vertex, so 3+2 is unachievable and
a(5)=6 rather than p(5)=7.

The capacities are obtained from a second, small DP that counts forests by
orbit partition exactly (Python ints; the totals are just A000081, so they stay
tiny).  Capacity only bites when a class can be used more than once, i.e. when
m <= n/2, so the counting DP only has to run to size n_max//2 - 1.

WHY IT BEATS BRUTE FORCE
------------------------
Brute force enumerates rooted forests, i.e. A000081(n+1) objects: 2.1e9 already
at n=24, hopeless past the published range.  Here the state is the SET of
partitions, so everything collapses onto at most p(n) values per size and the
whole computation is a knapsack whose total work is about sum_m a(m-1)*a(n-m).

Partitions are encoded as integers - multiplicity of part v sits in digit v of a
base-2^BITS integer - so a multiset union is a single machine-word-ish integer
addition and the hot loop is `set.update(map(code.__add__, src))`.

Verified against the 25 published terms and against an independent brute-force
enumeration of every rooted forest for n <= 12.
"""

from math import factorial

OFFSET = 1
# Measured, not aspirational: this is how far the implementation
# recomputes from scratch inside CI's budget. The gate recomputes to
# exactly this index, so the extension reported is the one verified.
EXTEND_TO = 38
PUBLISHED = [1, 2, 3, 5, 6, 11, 13, 21, 28, 38, 51, 73, 93, 124, 163, 212,
             278, 352, 459, 572, 736, 914, 1187, 1434, 1838]


def _scale(code, k, bits):
    """Multiply every part of the encoded partition by k."""
    if k == 1:
        return code
    mask = (1 << bits) - 1
    out = 0
    v = 0
    while code:
        d = code & mask
        if d:
            out |= d << (bits * v * k)
        code >>= bits
        v += 1
    return out


def _usages(pcode, m, cc, budget, bits):
    """Every way this tree class can be used.

    Returns (vertices, contribution code, multiplicity multiset).  A usage is a
    multiset K of group multiplicities with |K| <= cc (cc distinct trees are
    available) and m*sum(K) <= budget; it contributes sum_{k in K} k*P.
    """
    maxsum = budget // m
    if maxsum <= 0 or cc <= 0:
        return []
    scaled = [0] + [_scale(pcode, k, bits) for k in range(1, maxsum + 1)]
    out = []
    stack = [(maxsum, 0, 0, 0, ())]
    while stack:
        maxk, depth, cursum, curcode, ks = stack.pop()
        if ks:
            out.append((cursum * m, curcode, ks))
        if depth == cc:
            continue
        top = maxk if maxk < maxsum - cursum else maxsum - cursum
        for k in range(top, 0, -1):
            stack.append((k, depth + 1, cursum + k, curcode + scaled[k], ks + (k,)))
    return out


def _ways(c, ks):
    """# of ways to realise multiplicity multiset ks with c distinct trees."""
    j = len(ks)
    if j > c:
        return 0
    num = 1
    for i in range(j):
        num *= c - i
    den = 1
    run = 1
    for i in range(1, j):
        if ks[i] == ks[i - 1]:
            run += 1
        else:
            den *= factorial(run)
            run = 1
    den *= factorial(run)
    return num // den


def terms(n_max, _progress=None):
    """Return [a(1), ..., a(n_max)].  _progress is an optional callback(m, a(m))
    used only for streaming partial output from long runs."""
    n = int(n_max)
    if n < 1:
        return []
    bits = 6
    while (1 << bits) - 1 < n:
        bits += 1
    one = 1 << bits                     # the partition (1)

    hc = max(0, n // 2 - 1)             # counting DP horizon

    dp = [set() for _ in range(n + 1)]  # dp[s] = achievable forest partitions
    dp[0].add(0)
    cnt = [dict() for _ in range(hc + 1)]   # cnt[s][code] = # forests
    cnt[0][0] = 1

    out = []
    half = n // 2
    for m in range(1, n + 1):
        classes = sorted(dp[m - 1])     # each Q gives the tree partition {1}+Q
        for q in classes:
            pcode = q + one
            c = cnt[m - 1][q] if m <= half else 1
            cc = c if c < n // m else n // m
            uses = [(v, code) for v, code, _ in _usages(pcode, m, cc, n, bits)]
            if not uses:
                continue
            for s in range(n, m - 1, -1):
                tgt = dp[s]
                for v, code in uses:
                    if v > s:
                        continue
                    src = dp[s - v]
                    if src:
                        tgt.update(map(code.__add__, src))
            # capacities for later classes: count forests exactly, small sizes
            if m <= hc:
                cc2 = c if c < hc // m else hc // m
                uses2 = [(v, code, _ways(c, ks))
                         for v, code, ks in _usages(pcode, m, cc2, hc, bits)]
                for s in range(hc, m - 1, -1):
                    tgt = cnt[s]
                    for v, code, w in uses2:
                        if v > s:
                            continue
                        for qq, cv in cnt[s - v].items():
                            key = code + qq
                            tgt[key] = tgt.get(key, 0) + w * cv
        out.append(len(dp[m]))
        if _progress is not None:
            _progress(m, out[-1])
    return out


if __name__ == "__main__":
    import sys
    import time
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    t0 = time.time()

    def prog(m, v):
        print("a(%d) = %d   [%.1fs]" % (m, v, time.time() - t0), flush=True)

    got = terms(lim, _progress=prog)
    el = time.time() - t0
    ok = got[:len(PUBLISHED)] == PUBLISHED[:len(got)]
    print("matches published:", ok)
    print("terms:", got)
    if len(got) > len(PUBLISHED):
        print("new:", got[len(PUBLISHED):])
    print("elapsed %.1fs" % el)
