#!/usr/bin/env python3
"""One E016 verifier agent.

Runs on a worker node against a locally hosted open-weight model (llama-server,
OpenAI-compatible endpoint, so each model family's own chat template applies).
Reads the verification corpus, emits one verdict per task.

An agent is a point in the diversity space ADR-0008 hypothesises matters:
(model family, prompt template, temperature). Nothing here is a paid API -- the
model runs on the node's own CPU.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# Five genuinely different reasoning framings, not five paraphrases. The point is
# to see whether prompt diversity buys error independence the way model diversity
# is assumed to.
TEMPLATES = {
    "direct": (
        "You are reviewing code.\n\nSPEC:\n{spec}\n\nCODE:\n{code}\n\n"
        "Does the code correctly implement the spec for all valid inputs?\n"
        "Answer with exactly one word: YES or NO."
    ),
    "edge_cases": (
        "You are reviewing code.\n\nSPEC:\n{spec}\n\nCODE:\n{code}\n\n"
        "Think about edge cases: empty input, duplicates, negative numbers, "
        "ties, and boundary values.\n"
        "Then answer with exactly one word on the last line: YES if the code is "
        "correct for all valid inputs, NO if any case is wrong."
    ),
    "adversarial": (
        "You are a skeptical reviewer trying to REJECT incorrect code.\n\n"
        "SPEC:\n{spec}\n\nCODE:\n{code}\n\n"
        "Try to find an input where this code violates the spec. "
        "If you can find one, the code is wrong.\n"
        "Answer with exactly one word on the last line: NO if you found a "
        "failing input, YES if you are confident there is none."
    ),
    "test_writer": (
        "SPEC:\n{spec}\n\nCODE:\n{code}\n\n"
        "Imagine you wrote a thorough unit test suite for this spec. "
        "Would this code pass every test?\n"
        "Answer with exactly one word on the last line: YES or NO."
    ),
    "terse": (
        "Spec: {spec}\nCode:\n{code}\nCorrect? YES or NO."
    ),
}

VERDICT_RE = re.compile(r"\b(YES|NO)\b", re.IGNORECASE)


def ask(endpoint: str, model_hint: str, prompt: str, temperature: float,
        seed: int, timeout: float = 180.0) -> str:
    payload = {
        "model": model_hint,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "seed": seed,
        "max_tokens": 200,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body = json.load(fh)
    return body["choices"][0]["message"]["content"]


def parse_verdict(text: str):
    """Last YES/NO token wins -- models often reason first and conclude last."""
    hits = VERDICT_RE.findall(text or "")
    if not hits:
        return None
    return hits[-1].upper() == "YES"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--model", required=True, help="model family label")
    ap.add_argument("--template", required=True, choices=sorted(TEMPLATES))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    tasks = [json.loads(l) for l in open(args.tasks) if l.strip()]
    tmpl = TEMPLATES[args.template]

    done = set()
    if os.path.exists(args.out):                      # resume, never redo work
        for line in open(args.out):
            try:
                done.add(json.loads(line)["task_id"])
            except Exception:
                pass

    with open(args.out, "a") as fh:
        for i, t in enumerate(tasks):
            if t["task_id"] in done:
                continue
            prompt = tmpl.format(spec=t["spec"], code=t["candidate"])
            raw, err = "", None
            for attempt in range(args.retries + 1):
                try:
                    raw = ask(args.endpoint, args.model, prompt,
                              args.temperature, args.seed)
                    err = None
                    break
                except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
                    err = f"{type(e).__name__}: {e}"
                    time.sleep(3 * (attempt + 1))
            verdict = parse_verdict(raw) if err is None else None
            fh.write(json.dumps({
                "agent_id": args.agent_id,
                "model": args.model,
                "template": args.template,
                "temperature": args.temperature,
                "seed": args.seed,
                "task_id": t["task_id"],
                "verdict": verdict,          # True=viable, False=not, None=unparseable
                "error": err,
                "raw": (raw or "")[-400:],
            }, sort_keys=True) + "\n")
            fh.flush()
            if (i + 1) % 10 == 0:
                print(f"{args.agent_id}: {i+1}/{len(tasks)}", flush=True)

    print(f"{args.agent_id}: DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
