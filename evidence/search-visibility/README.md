# Search visibility evidence

This directory stores **observations**, not marketing claims.

The target map in `config/seo-topics-v1.json` contains 100 semantic search intents. This ledger records what is actually observed after deployment across Google, Bing, ChatGPT, Gemini, Claude, Perplexity, Copilot, Yahoo, and other surfaces.

## Files

- `observations.json` — canonical v0.1 observation ledger;
- `REPORT.md` — deterministic summary generated from the ledger;
- schema: `schemas/search-visibility-observation-v0.1.schema.json`;
- generator: `tools/search_visibility_report.py`.

## Evidence rules

An observation must say where and how it was observed. Accepted evidence classes are:

- `manual_reproduction` — a dated query on a named product surface;
- `webmaster_export` — Search Console, Bing Webmaster Tools, or equivalent first-party webmaster data;
- `referral_log` — a referral/analytics observation;
- `index_inspection` — first-party index inspection for a URL.

A single manual query is not a ranking probability, market-share estimate, or proof that every user will receive the same answer. Personalization, geography, time, experiments, model versions, and index freshness can change results.

Do not commit personal identifiers, account cookies, search history, private queries, or screenshots containing user data. Store only the minimum evidence needed to reproduce the observation.

## Generate a balanced observation worklist

Use `scripts/search_visibility_observation_plan.py` to avoid cherry-picking
queries or engines.

```bash
# 80 sentinel checks: ten cluster-head queries x eight primary surfaces
python scripts/search_visibility_observation_plan.py \
  --sample heads \
  --format csv \
  --output results/visibility/answer-engine-heads.csv

# 800 checks: all 100 canonical intents x eight primary surfaces
python scripts/search_visibility_observation_plan.py \
  --sample full \
  --format csv \
  --output results/visibility/answer-engine-full.csv
```

The worklist is not an observation ledger and makes no visibility claim. It is
only a deterministic queue of queries/surfaces to reproduce.

## Add an observation

1. Choose one of the 100 `mapped_intent` values from `config/seo-topics-v1.json`.
2. Record the actual `query` used; it may differ from the mapped phrase.
3. Record engine, surface, UTC observation time, intended IDKMesh target URL, whether it surfaced, and a concise note.
4. Add a citation URL or evidence reference only when one really exists.
5. Regenerate the report:

```bash
python tools/search_visibility_report.py > evidence/search-visibility/REPORT.md
```

6. Run the focused tests:

```bash
python -m pytest -q tests/test_search_visibility_report.py
```

The report intentionally does not average positions across unlike engines or turn manual answer-engine checks into a synthetic visibility score.
