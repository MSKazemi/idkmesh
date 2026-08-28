# Sequential evidence reproducibility hardening

Date: 2026-08-28

After PR #206 merged, the new Sequential Evidence Kernel passed on canonical `main` under both Python 3.11 and 3.13. The GitHub Actions artifact archives, however, had different archive-level digests even though the workflow itself was green.

That exposed an evidence-quality issue: an artifact archive digest can reflect packaging/container details and should not be used as a direct proof that the mathematical payload itself is byte-identical across interpreters.

## Hardening decision

Replace the two independent matrix jobs with one read-only job that performs both interpreter runs and then compares the actual generated JSON payloads directly:

```text
Python 3.11 -> compile -> tests -> demo-3.11.json
Python 3.13 -> compile -> tests -> demo-3.13.json
                         |
                         v
                   byte-for-byte cmp
                         |
                         v
                 explicit SHA-256 content hash
```

The job fails if the two JSON files differ at all. It then writes a SHA-256 over the content itself and retains both payloads plus the hash in one artifact.

This makes the reproducibility claim about the mathematical output, not about GitHub's archive packaging.

## Authority boundary

This hardening does not change the algorithm, confidence thresholds, governance decisions, repository permissions, or integration authority. The workflow remains:

```text
permissions: contents: read
```

`main` remains unprotected and that continues to be a separate hard governance boundary.
