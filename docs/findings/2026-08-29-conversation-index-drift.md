# Conversation Index Drift Review

**Source revision:** `30dc9c3cb6c580cf00e292c447d3cf0b48abe181`

**Scope:** `docs/conversations/`

**Related:** issue #152

## Finding

The conversation archive declared 146 records, but its index linked only 123 of
them. The 23 missing entries were retained project-memory records created after
the last index refresh. Nineteen appeared as `orphan_document_candidate`
warnings; four already had non-index references and therefore were not true
orphans. No record was generated, moved, deleted, or reclassified.

This is a confirmed directory-index maintenance gap, not evidence that the
historical records should become canonical guidance. Their own status remains
append-only project memory, and current decisions still belong in the canonical
artifacts named by `PROJECT_RULES.md`.

## Bounded correction

The archive index now links each of its 146 records exactly once. A focused
test checks both exact link coverage and the declared record count, and the
IDKGraph observatory workflow runs that test whenever the index, a conversation
record, or the test changes.

## Measured effect

The canonical observatory was run before and after the correction on the same
source revision and working tree, with its output written outside the scanned
repository.

| Finding | Before | After |
| --- | ---: | ---: |
| `orphan_document_candidate` | 42 | 23 |
| `document_referenced_only_by_non_markdown_artifact` | 12 | 11 |
| `docs/conversations/` findings | 19 | 0 |
| accepted-decision linkage warnings | 0 | 0 |
| unexpected deterministic errors | 0 | 0 |

The warning reduction is a consequence of repairing the declared exhaustive
index, not a standalone objective. No independent-human review minutes are
claimed; issue #167 remains the separate human-review gate for issue #152.

## Reproduction

```bash
python -m unittest tests.test_conversation_index -v
python tools/idkgraph_observatory.py . \
  --output-dir /tmp/idkgraph-observatory \
  --pretty
```
