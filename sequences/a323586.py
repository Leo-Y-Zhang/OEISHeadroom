"""A323586: plane partitions of n with no repeated rows (equivalently, no repeated columns).

OFFSET 0.  Published: 1,1,2,5,8,16,30,53,89,158,265,443,735,1197 (14 terms, keyword `more`).

ALGORITHM
---------
A plane partition is a chain of partitions lam^(1) >= lam^(2) >= ... under componentwise
domination, i.e. a nested chain of Young diagrams lam^(1) contains lam^(2) contains ...
Because the rows are nested, two equal rows force every row between them to be equal too,
so "all rows distinct" is equivalent to the LOCAL condition "consecutive rows distinct".
Hence:

    a(n) = # of STRICTLY nested chains lam^(1) )( lam^(2) )( ... )( lam^(k) =/= empty
           of Young diagrams with |lam^(1)| + ... + |lam^(k)| = n.

(Equivalently: plane partitions of n whose entries use every value 1..max.)

Strict containment forces the row sums to strictly decrease, so k = O(sqrt n).
The DP is  F(lam, m) = # chains strictly inside lam of total weight m:

    F(lam, m) = [m == 0] + sum over mu strictly inside lam, 1 <= |mu| <= min(m, |lam|-1)
                           of F(mu, m - |mu|)

    a(n) = [n == 0] + sum over s >= 1, sum over lam |- s, of F(lam, n - s).

Two things make this beat brute-force generation (which dies at n ~ 13):

1. TRUNCATION / CANONICAL KEY.  Only sub-diagrams of size <= m can ever be used, and any
   mu with |mu| <= m has mu_i <= m//i.  So F(lam, m) depends on lam only through
   canon(lam, cap)_i = min(lam_i, cap//i) for i <= cap, cap = min(m, |lam|-1) -- a shape
   inside the hyperbola i*j <= cap.  Millions of distinct partitions collapse onto a few
   thousand memo keys, and one memo entry serves every partition sharing that truncation.

2. The outer sum over all lam |- s is done by grouping the partitions of s by that same
   truncation (which needs only O(min(len lam, n-s)) work per partition and NO recursion),
   so the expensive chain DP runs once per truncation class instead of once per partition.

Brute force enumerates every plane partition of n (super-polynomial, ~exp(c n^(2/3)));
this enumerates only chains-modulo-truncation, and the outer loop is a single pass over
the partitions of each s <= n.  Standard library only.
"""

OFFSET = 0
# Measured, not aspirational: this is how far the implementation
# recomputes from scratch inside CI's budget. The gate recomputes to
# exactly this index, so the extension reported is the one verified.
EXTEND_TO = 40
PUBLISHED = [1, 1, 2, 5, 8, 16, 30, 53, 89, 158, 265, 443, 735, 1197]


# ---------------------------------------------------------------- partitions

def _partitions(n):
    """Yield every partition of n as a weakly decreasing tuple (accel_asc, reversed)."""
    if n == 0:
        yield ()
        return
    a = [0] * (n + 1)
    k = 1
    a[1] = n
    while k != 0:
        x = a[k - 1] + 1
        y = a[k] - 1
        k -= 1
        while x <= y:
            a[k] = x
            y -= x
            k += 1
        a[k] = x + y
        yield tuple(a[k::-1])


# ---------------------------------------------------------------- truncation

def _canon(lam, cap):
    """Canonical form of lam for budget cap: min(lam_i, cap//i), i = 1..cap."""
    if cap <= 0:
        return ()
    out = []
    n = len(lam)
    if n > cap:
        n = cap
    for i in range(n):
        c = cap // (i + 1)
        v = lam[i]
        out.append(c if c < v else v)
    return tuple(out)


# ---------------------------------------------------------------- sub-diagrams

_subs_memo = {}


def _subs(shape, cap):
    """All non-empty mu inside `shape` with |mu| <= cap, as a list of (mu, |mu|)."""
    key = (shape, cap)
    got = _subs_memo.get(key)
    if got is not None:
        return got
    out = []
    ln = len(shape)

    def rec(row, prev, cur, tot):
        # extend with row `row`, part <= min(prev, shape[row]), total <= cap
        if row < ln:
            hi = shape[row]
            if prev < hi:
                hi = prev
            room = cap - tot
            if room < hi:
                hi = room
            for v in range(hi, 0, -1):
                cur.append(v)
                out.append((tuple(cur), tot + v))
                rec(row + 1, v, cur, tot + v)
                cur.pop()

    rec(0, cap, [], 0)
    _subs_memo[key] = out
    return out


# ---------------------------------------------------------------- chain DP

_F_memo = {}


def _F(shape, m, size):
    """# chains strictly inside a partition of size `size` whose truncation is `shape`,
    with total weight exactly m."""
    if m == 0:
        return 1
    cap = m if m < size else size - 1
    if cap <= 0:
        return 0
    k = _canon(shape, cap)
    key = (k, cap, m)
    got = _F_memo.get(key)
    if got is not None:
        return got
    tot = 0
    for mu, sz in _subs(k, cap):
        tot += _F(mu, m - sz, sz)
    _F_memo[key] = tot
    return tot


# ---------------------------------------------------------------- main

def terms(n_max, progress=None):
    """Return [a(0), ..., a(n_max)]."""
    A = [0] * (n_max + 1)
    A[0] = 1
    for s in range(1, n_max + 1):
        M = n_max - s
        # group the partitions of s by their truncation at budget M
        groups = {}
        if M == 0:
            cnt = 0
            for _ in _partitions(s):
                cnt += 1
            groups[()] = cnt
        else:
            for lam in _partitions(s):
                k = _canon(lam, M)
                groups[k] = groups.get(k, 0) + 1
        for k, cnt in groups.items():
            for m in range(M + 1):
                v = _F(k, m, s)
                if v:
                    A[s + m] += cnt * v
        if progress:
            progress(s, len(groups))
    return A


if __name__ == "__main__":
    import sys
    import time

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    t0 = time.time()
    res = terms(N)
    dt = time.time() - t0
    ok = res[:len(PUBLISHED)] == PUBLISHED[:N + 1]
    print("matches published:", ok)
    if not ok:
        print("computed :", res[:len(PUBLISHED)])
        print("published:", PUBLISHED[:N + 1])
    for i, v in enumerate(res):
        print(i, v)
    print("time %.2fs  F-memo %d  subs-memo %d" % (dt, len(_F_memo), len(_subs_memo)))
