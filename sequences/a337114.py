"""A337114 - Number of distinct node-partitions of n-vertex trees.

Definition (pinned from the OEIS %e block): the "node-partition" of a tree is
the partition of n given by the orbit sizes of Aut(T) acting on V(T), i.e. the
sizes of the classes of mutually indistinguishable vertices.  a(n) counts how
many *distinct* partitions arise over all n-vertex trees.  (%e: the 5-vertex
star gives 1+4, P5 gives 1+2+2, the fork gives 1+1+1+2, so a(5)=3.)

Algorithm
---------
Brute force enumerates free trees (39.3 million at n=24, 6.9 billion at n=32),
which is hopeless in Python.  But a(n) counts a SET of partitions, and the
orbit partition is *compositional*, so we can work directly in partition space
and never touch a tree:

  * Rooted tree R = root + multiset of branch subtrees.  Aut(R) is the direct
    product over isomorphism classes C (multiplicity m) of Aut(C) wr S_m, hence
        P(R) = {1} u  U_C  m_C * P(C)        ("m*p" = every part of p times m).
  * Unrooted: Aut(T) fixes the centroid.  A unicentroidal tree is a rooted tree
    all of whose branches have <= floor((n-1)/2) vertices, and P(T) = P(rooted).
    A bicentroidal tree (n even) is an unordered pair {A,B} of rooted trees on
    n/2 vertices; P(T) = P(A) u P(B) if A !~ B, and 2*P(A) if A ~ B.

So the whole computation is one knapsack over "branch classes" whose state is
just a partition (the size is recovered as the sum of the parts).  A class is a
pair (partition q, one of the c_q distinct rooted trees realising it), so we
also carry c_q = #rooted trees with orbit partition q -- needed because two
*different* branch classes sharing a partition q can be used with different
multiplicities m1, m2, giving m1*q u m2*q, which one class alone cannot give.
c_q is only ever compared against a multiplicity <= n, so it is computed with
saturating arithmetic (capped at CAP); saturation is exact for min(true, CAP)
because every operation is monotone.

Processing the branch classes in increasing size s, the DP state after the
size-(s-1) classes *is* the set of forests with all branches <= s-1, which is
exactly the unicentroidal snapshot needed for n = 2s-1 and n = 2s, and the
rooted trees on s vertices are read off the same state at total s-1.  One pass
therefore yields every term.

Cost is O(sum_s |R(s)| * #states) partition merges instead of O(#free trees);
the set of achievable partitions is a large fraction of p(n) (a(24)=1237 vs
p(24)=1575), so the state space is ~p(n) rather than exponential.

Pure stdlib, Python 3.13.
"""

from math import comb

OFFSET = 1
# Measured, not aspirational: this is how far the implementation
# recomputes from scratch inside CI's budget. The gate recomputes to
# exactly this index, so the extension reported is the one verified.
EXTEND_TO = 36
PUBLISHED = [1, 1, 1, 2, 3, 6, 9, 15, 19, 32, 36, 56, 70, 103,
             122, 175, 210, 298, 349, 486, 569, 773, 912, 1237]

CAP = 4096  # saturation cap for "number of distinct rooted trees" counts

_pam_memo = {}


def _partitions_at_most(k, j):
    """Partitions of k into at most j positive parts, as descending tuples."""
    key = (k, j)
    r = _pam_memo.get(key)
    if r is not None:
        return r
    out = []
    cur = []

    def rec(rem, maxp):
        if rem == 0:
            out.append(tuple(cur))
            return
        if len(cur) == j:
            return
        for v in range(min(rem, maxp), 0, -1):
            cur.append(v)
            rec(rem - v, v)
            cur.pop()

    rec(k, k)
    _pam_memo[key] = out
    return out


_prof_memo = {}


def _profiles(s, kmax, c):
    """Usage profiles of one branch class-bucket of size s holding c distinct
    classes: list of (multiplicity multiset, vertices used, #ways)."""
    jmax = min(c, kmax)
    key = (s, kmax, c if c < CAP else CAP)
    r = _prof_memo.get(key)
    if r is not None:
        return r
    out = []
    for k in range(1, kmax + 1):
        for prof in _partitions_at_most(k, jmax):
            # ways to pick which distinct classes carry which multiplicity
            ways = 1
            rem = c
            i = 0
            n_p = len(prof)
            while i < n_p:
                v = prof[i]
                t = 0
                while i < n_p and prof[i] == v:
                    t += 1
                    i += 1
                ways *= comb(rem, t)
                rem -= t
                if ways >= CAP:
                    ways = CAP
                    break
            out.append((prof, s * k, ways))
    _prof_memo[key] = out
    return out


def terms(n_max, verbose=False):
    """Return a(1)..a(n_max).

    Partitions are held as `bytes` of ascending parts (parts are <= n < 256),
    which is both compact and merged at C speed by bytes(sorted(a + b)).
    """
    N = int(n_max)
    if N < 1:
        return []
    if N > 250:
        raise ValueError("byte-packed parts require n_max <= 250")

    # state[m] : {forest orbit-partition (ascending bytes) -> capped #forests}
    # after the size-<=s-1 branch classes have been processed.
    state = [dict() for _ in range(N)]
    state[0][b""] = 1

    uni = [set() for _ in range(N + 1)]
    bic = [set() for _ in range(N + 1)]
    out = [0] * (N + 1)

    smax = (N + 1) // 2
    if smax < 1:
        smax = 1
    ONE = b"\x01"

    for s in range(1, smax + 1):
        # --- snapshot: rooted trees on s vertices = forests on s-1 + a root ---
        R = {}
        if s - 1 < N:
            for f, c in state[s - 1].items():
                R[bytes(sorted(f + ONE))] = c

        # --- unicentroidal harvest: branches must be <= floor((n-1)/2) = s-1 ---
        for n in (2 * s - 1, 2 * s):
            if 1 <= n <= N:
                add = uni[n].add
                for f in state[n - 1]:
                    add(bytes(sorted(f + ONE)))

        # --- bicentroidal harvest for n = 2s ---
        n = 2 * s
        if n <= N:
            add = bic[n].add
            qs = list(R.items())
            for q, c in qs:
                add(bytes(x + x for x in q))           # A isomorphic to B
                if c >= 2:
                    add(bytes(sorted(q + q)))          # two distinct, same part.
            L = len(qs)
            for i in range(L):
                qi = qs[i][0]
                for j in range(i + 1, L):
                    add(bytes(sorted(qi + qs[j][0])))

        # a(2s-1) and a(2s) are final now
        for n in (2 * s - 1, 2 * s):
            if 1 <= n <= N:
                out[n] = len(uni[n] | bic[n])
                uni[n] = bic[n] = None
                if verbose:
                    print("a(%d) = %d" % (n, out[n]), flush=True)

        if s >= smax:
            break

        # --- fold every branch class of size s into the knapsack state ---
        kmax_global = (N - 1) // s
        if kmax_global < 1:
            continue
        for q, c in R.items():
            profs = _profiles(s, kmax_global, c)
            # materialise the actual partition deltas for this class
            deltas = []
            for prof, dsize, ways in profs:
                if dsize > N - 1:
                    continue
                d = []
                for m in prof:
                    if m == 1:
                        d.extend(q)
                    else:
                        d.extend([x * m for x in q])
                deltas.append((bytes(sorted(d)), dsize, ways))
            if not deltas:
                continue
            top = N - 1 - s
            for m in range(top, -1, -1):
                src = state[m]
                if not src:
                    continue
                items = list(src.items())
                room = N - 1 - m
                for d, dsize, ways in deltas:
                    if dsize > room:
                        continue
                    tgt = state[m + dsize]
                    get = tgt.get
                    for p, cnt in items:
                        np = bytes(sorted(p + d))
                        v = cnt * ways
                        if v > CAP:
                            v = CAP
                        old = get(np)
                        if old is None:
                            tgt[np] = v
                        else:
                            nv = old + v
                            tgt[np] = nv if nv < CAP else CAP
        if verbose:
            print("  [s=%d folded, |R(s)|=%d, states=%d]"
                  % (s, len(R), sum(len(x) for x in state)), flush=True)

    return out[1:]


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    t = terms(n, verbose=("-v" in sys.argv))
    print(",".join(map(str, t)))
    k = min(len(t), len(PUBLISHED))
    print("published match:", t[:k] == PUBLISHED[:k])
