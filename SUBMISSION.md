# OEIS submission pack

Everything needed to submit 7 extensions, in the order the OEIS form asks for
it. **Nothing here has been submitted.** Each block is copy-paste ready.

Generated from the verifier's real output by `make_submission.py`, so the terms
below are the ones `oeisheadroom verify` recomputes. If you change anything in
`sequences/`, regenerate this file rather than editing it.

## Before you paste anything

1. **Check it yourself.** `pip install -e . && oeisheadroom verify` reproduces
   all published terms and recomputes every new one in about a minute. If that
   does not come back clean, do not submit.
2. **Sign in at oeis.org, open the sequence, click "edit".** One sequence per
   draft. There is no hurry and no deadline.
3. **Edit only the two fields given below, plus the note.** No b-file. No new
   comment field. Smaller drafts get approved faster and argue less.
4. **The EXTENSIONS field ACCUMULATES.** Add your line *underneath* whatever is
   already there. Never retype or replace the existing lines -- that deletes
   someone else's credit, and it is what an editor bounced a previous draft of
   yours for.
5. **Write any reply to an editor in your own words.** That is the OEIS's
   policy and it is not negotiable. Do not paste anything generated here into a
   conversation with an editor.

Total across all 7 sequences: **123 new terms**, each one recomputed by a
program that first reproduces every already-published value exactly.

Repository, if an editor asks where the terms came from: https://github.com/Leo-Y-Zhang/OEISHeadroom

---


## A319381

> Number of plane trees with n nodes where the sequence of branches directly under any given node is a membership-chain.

Offset 1. Currently 22 published terms; this adds **28**, taking
the DATA line to 50 terms (242 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,1,1,2,2,4,6,9,11,20,28,40,58,82,110,159,217,305,420,570,767,1042,1390,1873,2494,3323,4376,5830,7655,10091,13281,17363,22633,29610,38419,50029,64812,84032,108529,140325,180808,233007,299489,384898,493435,633090,810069,1036427,1324168,1690879
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    (none - this sequence has no EXTENSIONS field yet, so your line is the first)
```

Add this as a NEW line, keeping anything above it:

```
a(23)-a(50) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 22 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## A323586

> Number of plane partitions of n with no repeated rows (or, equivalently, no repeated columns).

Offset 0. Currently 14 published terms; this adds **27**, taking
the DATA line to 41 terms (236 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,1,2,5,8,16,30,53,89,158,265,443,735,1197,1939,3127,4964,7844,12331,19192,29747,45837,70177,106882,162065,244407,366991,548722,816954,1211346,1789655,2633781,3862730,5645935,8224867,11944079,17292764,24961488,35928736,51572110,73827039
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    (none - this sequence has no EXTENSIONS field yet, so your line is the first)
```

Add this as a NEW line, keeping anything above it:

```
a(14)-a(40) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 14 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## A325555

> Number of necklace compositions of n with distinct differences up to sign.

Offset 1. Currently 25 published terms; this adds **16**, taking
the DATA line to 41 terms (185 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,2,2,4,5,6,10,15,19,24,39,49,78,106,155,207,313,430,608,867,1239,1670,2313,3220,4483,6066,8347,11522,15432,21094,28448,38750,52060,70635,93595,127353,169419,227569,301797,406086,537445
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    (none - this sequence has no EXTENSIONS field yet, so your line is the first)
```

Add this as a NEW line, keeping anything above it:

```
a(26)-a(41) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 25 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## A325556

> Number of necklace compositions of n with distinct circular differences up to sign.

Offset 1. Currently 25 published terms; this adds **17**, taking
the DATA line to 42 terms (179 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,1,1,1,1,1,3,7,9,13,25,27,51,63,95,123,179,205,305,409,559,715,1009,1337,1869,2479,3483,4675,6321,8613,11667,15769,21521,28719,38181,51655,67783,90825,119529,158677,206837,273913
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    (none - this sequence has no EXTENSIONS field yet, so your line is the first)
```

Add this as a NEW line, keeping anything above it:

```
a(26)-a(42) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 25 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## A337114

> Number of distinct node-partitions of n-vertex trees.

Offset 1. Currently 24 published terms; this adds **12**, taking
the DATA line to 36 terms (138 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,1,1,2,3,6,9,15,19,32,36,56,70,103,122,175,210,298,349,486,569,773,912,1237,1430,1910,2229,2913,3397,4431,5092,6619,7651,9727,11311,14280
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    %E a(13)-a(24) from _Bert Dobbelaere_, Aug 25 2020
```

> **Keep that line.** `a(13)-a(24) from _Bert Dobbelaere_, Aug 25 2020` must still be there when you save. Retyping the
> EXTENSIONS field instead of appending to it is exactly the edit that got a
> previous draft of yours reverted.

Add this as a NEW line, keeping anything above it:

```
a(25)-a(36) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 24 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## A347414

> Number of partitions of n which occur as the automorphism orbit sizes of a rooted forest of n vertices.

Offset 1. Currently 25 published terms; this adds **13**, taking
the DATA line to 38 terms (154 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,2,3,5,6,11,13,21,28,38,51,73,93,124,163,212,278,352,459,572,736,914,1187,1434,1838,2231,2821,3399,4308,5096,6457,7654,9516,11313,14004,16444,20411,23931
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    (none - this sequence has no EXTENSIONS field yet, so your line is the first)
```

Add this as a NEW line, keeping anything above it:

```
a(26)-a(38) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 25 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## A353403

> Number of compositions of n whose own reversed run-lengths are a subsequence (not necessarily consecutive).

Offset 0. Currently 18 published terms; this adds **10**, taking
the DATA line to 28 terms (116 chars, within the OEIS limit).

**1. DATA** -- replace the whole DATA field with this:

```
1,1,0,0,3,2,5,12,16,30,45,94,159,285,477,864,1487,2643,4588,8270,14381,25491,45054,79902,141055,249741,442169,783293
```

**2. EXTENSIONS** -- what the sequence carries right now:

```
    (none - this sequence has no EXTENSIONS field yet, so your line is the first)
```

Add this as a NEW line, keeping anything above it:

```
a(18)-a(27) from Leo Y. Zhang, Aug 30 2026
```

**3. Note for the submission box** (18 words):

```
Extended by an independent Python reimplementation that first reproduces all 18 published terms exactly. Verification and code: github.com/Leo-Y-Zhang/OEISHeadroom
```

All computed terms fit the DATA line.

---


## If an editor replies

Answer in your own words. The useful facts, in case you need them:

- The terms come from an independent reimplementation, not from the existing
  Mathematica program in the entry. The existing programs are brute force --
  for example A353403's takes every subset of every composition -- which is why
  these sequences stopped where they did.
- Correctness evidence is that each program reproduces **every** already-
  published term exactly before computing anything new. Several were also
  checked against a second, independently written brute force.
- Anyone can re-run the check: the repository's `verify` command recomputes the
  published terms and the new ones from scratch, and its CI does the same on
  every push.

**Do not chase a draft.** Sitting in `proposed` is normal and an editor will get
to it. If one asks for a change, make that change; if one reverts something,
read what they actually said before re-editing.
