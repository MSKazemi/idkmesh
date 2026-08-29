# IDKGraph Architecture Navigation Pass

**Source revision:** `10e7fcc06eecd008649d3ce66a8538a58fb98fc7`

**Scope:** `docs/architecture/` only

**Related:** issue #152

## Finding

The architecture directory contained 23 documents but no directory index. At
the source revision, six architecture documents were
`orphan_document_candidate` warnings and six were visible only through
non-Markdown workflow references. The remaining documents were reachable from
scattered pages, but there was no single map that distinguished executable,
experimental, proposed, and retired designs.

The affected cohort was reviewed by declared document status:

- active or working architecture: Agent Network, Independent Validator Runner,
  Opportunistic Compute Fabric, Repository Evolution Observatory, Free Resource
  Mesh, Repository Mathematical Portfolio, and Resource Compute Admission;
- experimental safeguards: Adversarial Evidence Envelope, Anytime Drift Guard,
  and Sequential Evidence Kernel;
- historical, non-canonical provenance: ONE Controller and ONE Agent Roles.

No document content, status, authority, or detector rule was changed. The new
index links all 23 documents by subsystem and explicitly isolates the retired
ONE designs. No independent-human review minutes are claimed; #167 remains the
human-attention and classification gate.

## Reproduction

```bash
python tools/idkgraph_observatory.py . \
  --output-dir /tmp/idkgraph-observatory \
  --pretty
```

| Finding | Before | After |
| --- | ---: | ---: |
| `orphan_document_candidate` | 47 | 41 |
| `document_referenced_only_by_non_markdown_artifact` | 18 | 12 |
| architecture findings | 12 | 0 |

The target is useful navigation and lifecycle clarity, not a zero-warning score.
Warnings outside this bounded directory remain untouched.
