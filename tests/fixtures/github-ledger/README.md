# C9-B local Git ledger fixture

This directory contains a **synthetic, deterministic** two-record chain for
issue #597 / C9-B.

- `00000000000000000001.json` is the first immutable record.
- `00000000000000000002.json` is the next record and binds the exact
  canonical digest of record 1 through `previous_record_digest`.
- `manifest.json` freezes both canonical record digests.

The record files are intentionally stored in the same compact canonical form
emitted by `idkmesh.github_ledger_serialization.serialize_github_ledger_record`:
UTF-8 canonical JSON plus one trailing LF.

`tests/test_github_ledger_serialization.py` creates a temporary local Git
repository, commits record 1, then commits record 2, and proves that the second
commit **only adds** the next record and leaves record 1 byte-identical.

The temporary `records/` layout used by that test is not the production
GitHub evidence-branch layout. C9-G owns that storage adapter/layout decision.
C9-C owns optimistic/concurrent append semantics.

These fixtures are protocol evidence only. They carry no dispatch,
verification, acceptance, Git-push, integration, or merge authority.
