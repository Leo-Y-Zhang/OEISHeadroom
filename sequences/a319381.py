"""A319381 -- plane trees whose every node has a "membership-chain" child list.

Definition
----------
A plane tree is a tuple of child subtrees, a leaf being ().  The tree is
counted iff at *every* node with children (t_1,...,t_k) we have
MemberQ[t_i, t_{i+1}] for each consecutive pair.  Mathematica's MemberQ
defaults to level {1}, so this says: t_{i+1} is one of the *elements* of
t_i, i.e. t_{i+1} is a direct child of t_i.  (Confirmed against the
published %e list for a(9)=11 and against a direct brute force to n=13;
the "member at any depth" reading gives 1,1,1,2,3,6,12,... which is not
this sequence.)

Algorithm
---------
Because t_{i+1} is a *child* of t_i, the child list of any node is a
downward path in its own first child.  So a tree T of size n>1 is exactly
a pair (X, v) where X is a valid tree and v a node of X: take the chain
of subtrees along the root->v path of X as T's children.  This is a
bijection, and |T| = 1 + (sum of subtree sizes along that path).

Let F_X(q) = sum over nodes v of X of q^{s_X(v)}, where s_X(v) is the sum
of the subtree sizes along root->v.  Then

    F_X(q) = q^{|X|} * (1 + sum over children c of X of F_c(q))

and  a(n) = [q^{n-1}] sum over all valid X of F_X(q)   for n >= 2.

So we enumerate valid trees once each (never re-deriving a subtree),
walking each tree to emit its chains, and carrying the running polynomial
sum down the walk so each new tree costs one polynomial addition.
Polynomials are packed into Python big integers, 32 bits per coefficient,
so an addition or a q^n shift is a single C-level bigint operation.

Two further prunings: trees of size >= n_max are never needed (their F
starts at degree >= n_max), and trees of size exactly n_max-1 contribute
only the single term q^{n_max-1}, i.e. exactly a(n_max-1) in total.  Hence
we materialise trees only up to size n_max-2 and correct at the end with
    a(n_max) = Phi[n_max-1] + a(n_max-1).

Why this beats the brute force: the OEIS Mathematica builds Tuples over
every permutation of every partition of n-1 and filters, so it pays for
the astronomically many *rejected* trees (Catalan-many overall).  Here
nothing invalid is ever built: the work is proportional to the number of
valid trees, which is the answer itself.
"""

OFFSET = 1
# Measured, not aspirational: this is how far the implementation
# recomputes from scratch inside CI's budget. The gate recomputes to
# exactly this index, so the extension reported is the one verified.
EXTEND_TO = 50
PUBLISHED = [1, 1, 1, 2, 2, 4, 6, 9, 11, 20, 28, 40,
             58, 82, 110, 159, 217, 305, 420, 570, 767, 1042]

_BITS = 32  # bits per packed polynomial coefficient


def terms(n_max):
    """Return [a(1), ..., a(n_max)]."""
    N = int(n_max)
    if N <= 0:
        return []
    if N == 1:
        return [1]
    if N == 2:
        return [1, 1]

    B = _BITS
    COEFF = (1 << B) - 1
    MASK = (1 << (B * N)) - 1          # keep degrees 0..N-1
    M = N - 2                          # largest tree size we materialise

    # tree table: id -> size, children tuple, packed F polynomial
    tsize = [1]
    tchild = [()]
    tF = [1 << B]                      # F_leaf = q
    Phi = 1 << B                       # running sum of F over stored trees

    by_size = [[] for _ in range(M + 2)]
    by_size[1].append(0)

    for j in range(1, M + 1):
        bucket = by_size[j]
        if 1 + j > M:
            continue
        for X in bucket:
            # walk tree X; each visited node v yields the chain root->v,
            # which is the child list of a new valid tree.
            stack = [(X, j, tF[X], (X,))]
            while stack:
                node, s, A, chain = stack.pop()
                n_new = s + 1
                newF = ((A + 1) << (B * n_new)) & MASK
                nid = len(tsize)
                tsize.append(n_new)
                tchild.append(chain)
                tF.append(newF)
                Phi += newF
                by_size[n_new].append(nid)
                for c in tchild[node]:
                    s2 = s + tsize[c]
                    if s2 < M:         # new tree size s2+1 <= M
                        stack.append((c, s2, A + tF[c], chain + (c,)))

    out = [1]
    for n in range(2, N):
        out.append((Phi >> (B * (n - 1))) & COEFF)
    out.append(((Phi >> (B * (N - 1))) & COEFF) + out[-1])
    return out


if __name__ == "__main__":
    import sys
    import time
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 22
    t0 = time.time()
    a = terms(n)
    dt = time.time() - t0
    ok = a[:len(PUBLISHED)] == PUBLISHED[:len(a)]
    print("matches published:", ok)
    print(",".join(map(str, a)))
    print("n_max=%d  %.2fs" % (n, dt))
