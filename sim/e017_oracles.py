#!/usr/bin/env python3
"""Input-region generators for E017: partial test oracles as real verifiers.

E016 tried to measure verifier error correlation with LLM judges and failed --
none of them discriminated. The obstacle was verifier competence, not the
question. This module builds verifiers that demonstrably do discriminate:
partial test oracles, each sampling inputs from one named REGION of a problem's
input domain.

That construction is the point. A real CI panel is a set of partial, imperfect
oracles, and two of them miss the same defect when they probe the same part of
the input space. Region membership is therefore a declared independence label of
exactly the kind ADR-0008 hypothesises -- and because these verifiers produce
real error vectors on real code, the correlation between them can be MEASURED
rather than assumed.

Expected outputs are never hand-written: they come from executing the problem's
reference ("ok") implementation, so the oracle cannot encode my own mistake
about what a function should return.
"""

from __future__ import annotations

import random
import string

# Region names shared by every generator family. Not every family populates
# every region; callers must tolerate an empty draw.
REGIONS = ("tiny", "small", "large", "extreme", "duplicate")


def _ints(rng, n, lo=-50, hi=50):
    return [rng.randint(lo, hi) for _ in range(n)]


def _sorted_ints(rng, n, lo=-50, hi=50):
    return sorted(_ints(rng, n, lo, hi))


def _region_size(rng, region):
    return {
        "tiny": rng.choice([0, 1]),
        "small": rng.randint(2, 4),
        "large": rng.randint(8, 20),
        "extreme": rng.randint(1, 3),
        "duplicate": rng.randint(4, 8),
    }[region]


def gen_int_list(rng, region, *, nonempty=False, distinct=False):
    n = _region_size(rng, region)
    if nonempty:
        n = max(1, n)
    if region == "extreme":
        xs = [rng.choice([0, -1, 1, 10**6, -(10**6)]) for _ in range(n)]
    elif region == "duplicate":
        pool = _ints(rng, max(1, n // 3))
        xs = [rng.choice(pool) for _ in range(n)]
    else:
        xs = _ints(rng, n)
    if distinct:
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        xs = out
    return xs


def gen_string(rng, region):
    n = _region_size(rng, region)
    if region == "extreme":
        alphabet = " \t\n.,:!?'"
    elif region == "duplicate":
        alphabet = "aab"
    else:
        alphabet = string.ascii_letters + "  .,"
    return "".join(rng.choice(alphabet) for _ in range(n))


def gen_words(rng, region):
    n = max(1, _region_size(rng, region))
    pool = ["a", "b", "the", "cat", "Dog", "a"] if region == "duplicate" else \
           ["alpha", "Beta", "gamma", "delta", "eps"]
    return " ".join(rng.choice(pool) for _ in range(n))


# ---------------------------------------------------------------------------
# Per-problem argument generators. Each returns a tuple of positional args.
# Constraints in the problem statements (non-empty, at least two distinct
# values, sorted inputs, non-zero divisor) are respected so that a rejection is
# always a real defect and never an out-of-contract input.
# ---------------------------------------------------------------------------

def _two_distinct(rng, region):
    xs = gen_int_list(rng, region, nonempty=True)
    while len(set(xs)) < 2:
        xs.append(rng.randint(-50, 50))
    return xs


GENERATORS = {
    "median_of_list": lambda r, g: (gen_int_list(r, g, nonempty=True),),
    "second_largest": lambda r, g: (_two_distinct(r, g),),
    "count_vowels": lambda r, g: (gen_string(r, g),),
    "chunk_list": lambda r, g: (gen_int_list(r, g), r.randint(1, 4)),
    "is_palindrome": lambda r, g: (gen_string(r, g),),
    "merge_sorted": lambda r, g: (_sorted_ints(r, _region_size(r, g)),
                                  _sorted_ints(r, _region_size(r, g))),
    "running_total": lambda r, g: (gen_int_list(r, g),),
    "word_frequencies": lambda r, g: (gen_words(r, g),),
    "clamp_value": lambda r, g: _clamp_args(r, g),
    "remove_duplicates_stable": lambda r, g: (gen_int_list(r, g),),
    "fizzbuzz_value": lambda r, g: (r.choice([3, 5, 15, 1, 30, 7, 9, 25])
                                    if g != "extreme" else r.choice([0, 1, 10**6]),),
    "binary_search": lambda r, g: _binary_search_args(r, g),
    "flatten_one_level": lambda r, g: ([gen_int_list(r, g)
                                        for _ in range(max(1, _region_size(r, g) // 2))],),
    "safe_divide": lambda r, g: (r.randint(-40, 40),
                                 r.choice([1, -1, 2, 3, 7]) if g != "extreme"
                                 else r.choice([0, 1, -1])),
    "title_case": lambda r, g: (gen_words(r, g),),
    "intersection_sorted": lambda r, g: (_sorted_ints(r, _region_size(r, g)),
                                         _sorted_ints(r, _region_size(r, g))),
    "max_subarray_sum": lambda r, g: (gen_int_list(r, g, nonempty=True),),
    "roman_value": lambda r, g: (r.choice(["IV", "IX", "MCMXCIV", "III", "LVIII", "XL", "I"]),),
    "group_by_parity": lambda r, g: (gen_int_list(r, g),),
    "trim_whitespace_lines": lambda r, g: ("\n".join(gen_string(r, g)
                                                     for _ in range(max(1, _region_size(r, g) // 2))),),
    "pairs_summing_to": lambda r, g: (gen_int_list(r, g), r.randint(-10, 10)),
    "normalise_scores": lambda r, g: (gen_int_list(r, g, nonempty=True),),
    "first_non_repeating": lambda r, g: (gen_string(r, g),),
    "days_between_indexes": lambda r, g: ([r.random() < 0.5
                                           for _ in range(max(1, _region_size(r, g)))],),
}


def _clamp_args(rng, region):
    lo = rng.randint(-20, 20)
    hi = lo + rng.randint(0, 20)
    if region == "extreme":
        value = rng.choice([lo, hi, lo - 1, hi + 1])
    else:
        value = rng.randint(lo - 10, hi + 10)
    return (value, lo, hi)


def _binary_search_args(rng, region):
    xs = sorted(set(_sorted_ints(rng, max(1, _region_size(rng, region)))))
    target = rng.choice(xs) if xs and rng.random() < 0.7 else rng.randint(-60, 60)
    return (xs, target)


def draw_inputs(problem, region, count, seed):
    """Deterministically draw `count` argument tuples for `problem` in `region`."""
    rng = random.Random(f"{problem}/{region}/{seed}")
    gen = GENERATORS[problem]
    out = []
    for _ in range(count):
        try:
            out.append(gen(rng, region))
        except Exception:
            continue
    return out
