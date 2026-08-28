#!/usr/bin/env python3
"""Build the E016 verification corpus.

Each task is a spec plus a candidate implementation. Ground truth is not a
judgement call: it is decided by executing hidden tests against the candidate in
a subprocess. A candidate is VIABLE iff every hidden test passes.

The point of the corpus is to give real LLM verifiers something with a knowable
right answer, so their error indicators -- and therefore their pairwise error
correlation -- can be measured rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# (name, spec, {variant: source}, hidden_tests)
# Exactly one variant per problem is correct by construction; the rest carry a
# single realistic defect. Ground truth is still established by execution, never
# by that labelling -- if a "buggy" mutant happens to pass, it is recorded VIABLE.
PROBLEMS = [
    (
        "median_of_list",
        "Return the median of a non-empty list of numbers. For an even-length list return the mean of the two middle values.",
        {
            "ok": "def solve(xs):\n    s = sorted(xs)\n    n = len(s)\n    m = n // 2\n    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2",
            "no_sort": "def solve(xs):\n    n = len(xs)\n    m = n // 2\n    return xs[m] if n % 2 else (xs[m - 1] + xs[m]) / 2",
            "int_div": "def solve(xs):\n    s = sorted(xs)\n    n = len(s)\n    m = n // 2\n    return s[m] if n % 2 else (s[m - 1] + s[m]) // 2",
        },
        [("solve([3,1,2])", 2), ("solve([1,2,3,4])", 2.5), ("solve([5])", 5), ("solve([4,1,3,2])", 2.5)],
    ),
    (
        "second_largest",
        "Return the second largest DISTINCT value in a list with at least two distinct values.",
        {
            "ok": "def solve(xs):\n    return sorted(set(xs))[-2]",
            "dupes": "def solve(xs):\n    return sorted(xs)[-2]",
            "off_by_one": "def solve(xs):\n    return sorted(set(xs))[-3]",
        },
        [("solve([1,2,3])", 2), ("solve([5,5,4])", 4), ("solve([9,1,9,7])", 7), ("solve([2,1])", 1)],
    ),
    (
        "count_vowels",
        "Count vowels (a,e,i,o,u) in a string, case-insensitive.",
        {
            "ok": "def solve(s):\n    return sum(1 for c in s.lower() if c in 'aeiou')",
            "case": "def solve(s):\n    return sum(1 for c in s if c in 'aeiou')",
            "y_included": "def solve(s):\n    return sum(1 for c in s.lower() if c in 'aeiouy')",
        },
        [("solve('hello')", 2), ("solve('HELLO')", 2), ("solve('xyz')", 0), ("solve('AeIoU')", 5)],
    ),
    (
        "chunk_list",
        "Split a list into consecutive chunks of size n. The final chunk may be shorter.",
        {
            "ok": "def solve(xs, n):\n    return [xs[i:i+n] for i in range(0, len(xs), n)]",
            "drops_tail": "def solve(xs, n):\n    return [xs[i:i+n] for i in range(0, len(xs) - len(xs) % n, n)]",
            "step_one": "def solve(xs, n):\n    return [xs[i:i+n] for i in range(0, len(xs))]",
        },
        [("solve([1,2,3,4,5],2)", [[1,2],[3,4],[5]]), ("solve([1,2,3,4],2)", [[1,2],[3,4]]),
         ("solve([1],3)", [[1]])],
    ),
    (
        "is_palindrome",
        "Return True if the string is a palindrome ignoring case and non-alphanumeric characters.",
        {
            "ok": "def solve(s):\n    t = [c.lower() for c in s if c.isalnum()]\n    return t == t[::-1]",
            "keeps_punct": "def solve(s):\n    t = s.lower()\n    return t == t[::-1]",
            "case_sensitive": "def solve(s):\n    t = [c for c in s if c.isalnum()]\n    return t == t[::-1]",
        },
        [("solve('A man, a plan, a canal: Panama')", True), ("solve('abc')", False),
         ("solve('Aa')", True), ("solve('ab_ba')", True)],
    ),
    (
        "merge_sorted",
        "Merge two sorted lists into one sorted list, keeping duplicates.",
        {
            "ok": "def solve(a, b):\n    out=[]; i=j=0\n    while i<len(a) and j<len(b):\n        if a[i]<=b[j]: out.append(a[i]); i+=1\n        else: out.append(b[j]); j+=1\n    return out+a[i:]+b[j:]",
            "drops_tail": "def solve(a, b):\n    out=[]; i=j=0\n    while i<len(a) and j<len(b):\n        if a[i]<=b[j]: out.append(a[i]); i+=1\n        else: out.append(b[j]); j+=1\n    return out",
            "dedups": "def solve(a, b):\n    return sorted(set(a+b))",
        },
        [("solve([1,3],[2,4])", [1,2,3,4]), ("solve([1,1],[1])", [1,1,1]),
         ("solve([],[2])", [2]), ("solve([5],[])", [5])],
    ),
    (
        "running_total",
        "Return the running cumulative sums of a list.",
        {
            "ok": "def solve(xs):\n    out=[]; t=0\n    for x in xs:\n        t+=x; out.append(t)\n    return out",
            "off_by_one": "def solve(xs):\n    out=[]; t=0\n    for x in xs:\n        out.append(t); t+=x\n    return out",
            "resets": "def solve(xs):\n    return [sum(xs[i:i+1]) for i in range(len(xs))]",
        },
        [("solve([1,2,3])", [1,3,6]), ("solve([])", []), ("solve([5])", [5]), ("solve([1,-1,2])", [1,0,2])],
    ),
    (
        "word_frequencies",
        "Return a dict mapping each whitespace-separated word to its count, lowercased.",
        {
            "ok": "def solve(s):\n    d={}\n    for w in s.lower().split():\n        d[w]=d.get(w,0)+1\n    return d",
            "case": "def solve(s):\n    d={}\n    for w in s.split():\n        d[w]=d.get(w,0)+1\n    return d",
            "chars": "def solve(s):\n    d={}\n    for w in s.lower():\n        d[w]=d.get(w,0)+1\n    return d",
        },
        [("solve('a b a')", {"a":2,"b":1}), ("solve('A a')", {"a":2}), ("solve('')", {})],
    ),
    (
        "clamp_value",
        "Clamp x into the inclusive range [lo, hi].",
        {
            "ok": "def solve(x, lo, hi):\n    return max(lo, min(x, hi))",
            "swapped": "def solve(x, lo, hi):\n    return min(lo, max(x, hi))",
            "exclusive": "def solve(x, lo, hi):\n    return x if lo < x < hi else (lo if x <= lo else hi)",
        },
        [("solve(5,1,10)", 5), ("solve(0,1,10)", 1), ("solve(11,1,10)", 10), ("solve(1,1,10)", 1)],
    ),
    (
        "remove_duplicates_stable",
        "Remove duplicates from a list, preserving first-occurrence order.",
        {
            "ok": "def solve(xs):\n    seen=set(); out=[]\n    for x in xs:\n        if x not in seen:\n            seen.add(x); out.append(x)\n    return out",
            "unstable": "def solve(xs):\n    return sorted(set(xs))",
            "keeps_last": "def solve(xs):\n    out=[]\n    for i,x in enumerate(xs):\n        if x not in xs[i+1:]: out.append(x)\n    return out",
        },
        [("solve([3,1,3,2])", [3,1,2]), ("solve([1,1,1])", [1]), ("solve([])", [])],
    ),
    (
        "fizzbuzz_value",
        "For n: return 'FizzBuzz' if divisible by 15, 'Fizz' if by 3, 'Buzz' if by 5, else str(n).",
        {
            "ok": "def solve(n):\n    if n%15==0: return 'FizzBuzz'\n    if n%3==0: return 'Fizz'\n    if n%5==0: return 'Buzz'\n    return str(n)",
            "order": "def solve(n):\n    if n%3==0: return 'Fizz'\n    if n%5==0: return 'Buzz'\n    if n%15==0: return 'FizzBuzz'\n    return str(n)",
            "int_return": "def solve(n):\n    if n%15==0: return 'FizzBuzz'\n    if n%3==0: return 'Fizz'\n    if n%5==0: return 'Buzz'\n    return n",
        },
        [("solve(15)", "FizzBuzz"), ("solve(3)", "Fizz"), ("solve(5)", "Buzz"), ("solve(7)", "7")],
    ),
    (
        "binary_search",
        "Return the index of target in a sorted list, or -1 if absent.",
        {
            "ok": "def solve(xs, t):\n    lo, hi = 0, len(xs)-1\n    while lo <= hi:\n        m=(lo+hi)//2\n        if xs[m]==t: return m\n        if xs[m]<t: lo=m+1\n        else: hi=m-1\n    return -1",
            "infinite_bound": "def solve(xs, t):\n    lo, hi = 0, len(xs)-1\n    while lo < hi:\n        m=(lo+hi)//2\n        if xs[m]==t: return m\n        if xs[m]<t: lo=m+1\n        else: hi=m-1\n    return -1",
            "returns_bool": "def solve(xs, t):\n    return t in xs",
        },
        [("solve([1,3,5,7],5)", 2), ("solve([1,3,5,7],1)", 0), ("solve([1,3,5,7],9)", -1),
         ("solve([1,3,5,7],7)", 3)],
    ),
    (
        "flatten_one_level",
        "Flatten a list of lists by exactly one level.",
        {
            "ok": "def solve(xs):\n    out=[]\n    for s in xs:\n        out.extend(s)\n    return out",
            "deep": "def solve(xs):\n    out=[]\n    def rec(v):\n        if isinstance(v, list):\n            for i in v: rec(i)\n        else: out.append(v)\n    rec(xs)\n    return out",
            "append": "def solve(xs):\n    out=[]\n    for s in xs:\n        out.append(s)\n    return out",
        },
        [("solve([[1,2],[3]])", [1,2,3]), ("solve([[[1]],[2]])", [[1],2]), ("solve([])", [])],
    ),
    (
        "safe_divide",
        "Return a/b, or None when b is zero.",
        {
            "ok": "def solve(a, b):\n    return None if b == 0 else a / b",
            "zero_return": "def solve(a, b):\n    return 0 if b == 0 else a / b",
            "int_div": "def solve(a, b):\n    return None if b == 0 else a // b",
        },
        [("solve(6,3)", 2.0), ("solve(1,0)", None), ("solve(7,2)", 3.5), ("solve(-6,3)", -2.0)],
    ),
    (
        "title_case",
        "Capitalise the first letter of each whitespace-separated word, lowercasing the rest.",
        {
            "ok": "def solve(s):\n    return ' '.join(w[:1].upper()+w[1:].lower() for w in s.split())",
            "no_lower": "def solve(s):\n    return ' '.join(w[:1].upper()+w[1:] for w in s.split())",
            "all_upper": "def solve(s):\n    return s.upper()",
        },
        [("solve('hello world')", "Hello World"), ("solve('hELLO')", "Hello"), ("solve('a b')", "A B")],
    ),
    (
        "intersection_sorted",
        "Return the sorted list of values present in BOTH lists, without duplicates.",
        {
            "ok": "def solve(a, b):\n    return sorted(set(a) & set(b))",
            "union": "def solve(a, b):\n    return sorted(set(a) | set(b))",
            "keeps_dupes": "def solve(a, b):\n    return sorted([x for x in a if x in b])",
        },
        [("solve([1,2,3],[2,3,4])", [2,3]), ("solve([1,1,2],[1,2])", [1,2]), ("solve([1],[2])", [])],
    ),
    (
        "max_subarray_sum",
        "Return the maximum sum of any non-empty contiguous subarray.",
        {
            "ok": "def solve(xs):\n    best=cur=xs[0]\n    for x in xs[1:]:\n        cur=max(x, cur+x)\n        best=max(best, cur)\n    return best",
            "zero_floor": "def solve(xs):\n    best=cur=0\n    for x in xs:\n        cur=max(0, cur+x)\n        best=max(best, cur)\n    return best",
            "total": "def solve(xs):\n    return sum(xs)",
        },
        [("solve([1,-2,3,4])", 7), ("solve([-3,-1,-2])", -1), ("solve([2,2])", 4)],
    ),
    (
        "roman_value",
        "Convert a Roman numeral string (I,V,X,L,C,D,M) to an integer, handling subtractive pairs.",
        {
            "ok": "def solve(s):\n    v={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n    t=0\n    for i,c in enumerate(s):\n        if i+1<len(s) and v[c]<v[s[i+1]]: t-=v[c]\n        else: t+=v[c]\n    return t",
            "no_sub": "def solve(s):\n    v={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n    return sum(v[c] for c in s)",
            "wrong_cmp": "def solve(s):\n    v={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n    t=0\n    for i,c in enumerate(s):\n        if i+1<len(s) and v[c]>v[s[i+1]]: t-=v[c]\n        else: t+=v[c]\n    return t",
        },
        [("solve('IV')", 4), ("solve('XIV')", 14), ("solve('MCMXC')", 1990), ("solve('III')", 3)],
    ),
    (
        "group_by_parity",
        "Return a dict with keys 'even' and 'odd' mapping to lists of the matching values, order preserved.",
        {
            "ok": "def solve(xs):\n    return {'even':[x for x in xs if x%2==0], 'odd':[x for x in xs if x%2!=0]}",
            "neg_mod": "def solve(xs):\n    return {'even':[x for x in xs if x%2==0], 'odd':[x for x in xs if x%2==1]}",
            "swapped": "def solve(xs):\n    return {'even':[x for x in xs if x%2!=0], 'odd':[x for x in xs if x%2==0]}",
        },
        [("solve([1,2,3])", {"even":[2],"odd":[1,3]}), ("solve([-3,-2])", {"even":[-2],"odd":[-3]}),
         ("solve([])", {"even":[],"odd":[]})],
    ),
    (
        "trim_whitespace_lines",
        "Strip leading/trailing whitespace from every line and drop lines that become empty.",
        {
            "ok": "def solve(s):\n    return [l.strip() for l in s.split('\\n') if l.strip()]",
            "keeps_empty": "def solve(s):\n    return [l.strip() for l in s.split('\\n')]",
            "no_strip": "def solve(s):\n    return [l for l in s.split('\\n') if l.strip()]",
        },
        [("solve('a\\n  b  \\n\\n c')", ["a","b","c"]), ("solve('  ')", []), ("solve('x')", ["x"])],
    ),
    (
        "pairs_summing_to",
        "Return the count of index pairs i<j whose values sum to target.",
        {
            "ok": "def solve(xs, t):\n    n=0\n    for i in range(len(xs)):\n        for j in range(i+1, len(xs)):\n            if xs[i]+xs[j]==t: n+=1\n    return n",
            "self_pair": "def solve(xs, t):\n    n=0\n    for i in range(len(xs)):\n        for j in range(i, len(xs)):\n            if xs[i]+xs[j]==t: n+=1\n    return n",
            "double_count": "def solve(xs, t):\n    n=0\n    for i in range(len(xs)):\n        for j in range(len(xs)):\n            if i!=j and xs[i]+xs[j]==t: n+=1\n    return n",
        },
        [("solve([1,2,3],4)", 1), ("solve([2,2,2],4)", 3), ("solve([1],2)", 0)],
    ),
    (
        "normalise_scores",
        "Scale a list of numbers to the range 0..1 by min-max. If all values are equal return zeros.",
        {
            "ok": "def solve(xs):\n    lo, hi = min(xs), max(xs)\n    if hi == lo: return [0.0]*len(xs)\n    return [(x-lo)/(hi-lo) for x in xs]",
            "div_zero": "def solve(xs):\n    lo, hi = min(xs), max(xs)\n    return [(x-lo)/(hi-lo) for x in xs]",
            "no_shift": "def solve(xs):\n    hi = max(xs)\n    if hi == 0: return [0.0]*len(xs)\n    return [x/hi for x in xs]",
        },
        [("solve([0,5,10])", [0.0,0.5,1.0]), ("solve([3,3])", [0.0,0.0]), ("solve([1,2])", [0.0,1.0])],
    ),
    (
        "first_non_repeating",
        "Return the first character that appears exactly once, or None.",
        {
            "ok": "def solve(s):\n    for c in s:\n        if s.count(c)==1: return c\n    return None",
            "last": "def solve(s):\n    r=None\n    for c in s:\n        if s.count(c)==1: r=c\n    return r",
            "empty_str": "def solve(s):\n    for c in s:\n        if s.count(c)==1: return c\n    return ''",
        },
        [("solve('aabbc')", "c"), ("solve('abcab')", "c"), ("solve('aa')", None), ("solve('xy')", "x")],
    ),
    (
        "days_between_indexes",
        "Given a list of booleans, return the largest gap (in indexes) between two consecutive True values, or 0 if fewer than two.",
        {
            "ok": "def solve(xs):\n    idx=[i for i,v in enumerate(xs) if v]\n    if len(idx)<2: return 0\n    return max(b-a for a,b in zip(idx, idx[1:]))",
            "min_gap": "def solve(xs):\n    idx=[i for i,v in enumerate(xs) if v]\n    if len(idx)<2: return 0\n    return min(b-a for a,b in zip(idx, idx[1:]))",
            "count": "def solve(xs):\n    return sum(1 for v in xs if v)",
        },
        [("solve([True,False,True])", 2), ("solve([True,True])", 1), ("solve([False])", 0),
         ("solve([True,False,False,True,True])", 3)],
    ),
]


def ground_truth(source: str, tests: list) -> bool:
    """Execute the candidate against hidden tests in a subprocess."""
    body = source + "\n\n_checks = [\n"
    for expr, expected in tests:
        body += f"    ({expr!r}, {expected!r}),\n"
    body += "]\n"
    body += (
        "import sys\n"
        "for _expr, _exp in _checks:\n"
        "    try:\n"
        "        _got = eval(_expr)\n"
        "    except Exception:\n"
        "        sys.exit(1)\n"
        "    if _got != _exp or type(_got) is not type(_exp):\n"
        "        sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(body)
        path = fh.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, timeout=10)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        Path(path).unlink(missing_ok=True)


def build() -> list:
    tasks = []
    for name, spec, variants, tests in PROBLEMS:
        for variant, src in variants.items():
            tasks.append({
                "task_id": f"{name}::{variant}",
                "problem": name,
                "variant": variant,
                "spec": spec,
                "candidate": src,
                "viable": ground_truth(src, tests),
            })
    return tasks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="benchmarks/e016-verification-corpus/tasks.jsonl")
    args = ap.parse_args()
    tasks = build()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        for t in tasks:
            fh.write(json.dumps(t, sort_keys=True) + "\n")
    n_ok = sum(t["viable"] for t in tasks)
    print(f"tasks: {len(tasks)}  viable: {n_ok}  non-viable: {len(tasks)-n_ok}")
    mislabelled = [t["task_id"] for t in tasks
                   if (t["variant"] == "ok") != t["viable"]]
    print(f"variants whose execution disagrees with their label: {len(mislabelled)}")
    for m in mislabelled:
        print(f"  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
