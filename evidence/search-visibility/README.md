# Search visibility evidence

This directory stores **observations**, not marketing claims.

The target map in `config/seo-topics-v1.json` contains 100 semantic search intents. The balanced observation plan covers 16 named search/answer surfaces across Google, Microsoft, Yahoo, DuckDuckGo, Brave, Apple, Amazon, Meta, OpenAI, Google Gemini, Anthropic, Perplexity, xAI, Mistral, and You.com products.

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
# 160 sentinel checks: ten cluster-head queries x sixteen primary surfaces
python scripts/search_visibility_observation_plan.py \
  --sample heads \
  --format csv \
  --output results/visibility/answer-engine-heads.csv

# 1,600 checks: all 100 canonical intents x sixteen primary surfaces
python scripts/search_visibility_observation_plan.py \
  --sample full \
  --format csv \
  --output results/visibility/answer-engine-full.csv
```

The worklist is not an observation ledger and makes no visibility claim. It is
only a deterministic queue of queries/surfaces to reproduce.

## Complete and import a worklist

Generate a fillable CSV template from the same deterministic plan:

```bash
# 160 sentinel rows
python scripts/search_visibility_observation_import.py \
  --template heads > /tmp/idkmesh-search-heads.csv

# 1,600 full rows
python scripts/search_visibility_observation_import.py \
  --template full > /tmp/idkmesh-search-full.csv
```

The plan-controlled columns must not be edited:

- `plan_id`
- `engine`
- `product_surface`
- `surface`
- `evidence_class`
- `cluster`
- `mapped_intent`
- `query`
- `target_url`

For a row that was actually reproduced, fill:

- `observed_at` — timezone-aware ISO 8601 timestamp;
- `surfaced` — exactly `true` or `false`;
- `position` — optional positive integer when the named surface exposes an
  ordered position;
- `citation_url` — optional URL actually surfaced/cited;
- `evidence_ref` — optional minimal reproducibility reference;
- `notes` — required concise observation note.

Then produce a **candidate** ledger:

```bash
python scripts/search_visibility_observation_import.py \
  --input /tmp/idkmesh-search-heads.csv \
  --output /tmp/observations.candidate.json
```

The importer revalidates every plan-controlled field against the canonical
1,600-item worklist, rejects invalid timestamps and impossible negative-result
claims, generates deterministic observation IDs, and refuses to overwrite the
canonical ledger directly.

Review the candidate diff before replacing
`evidence/search-visibility/observations.json`. After a reviewed ledger change,
regenerate `REPORT.md` and run the focused visibility tests.

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
