# C6 Provider-Neutral Candidate Normalization Fixture

This fixture is durable acceptance evidence for issue #579 / C6-G.

It intentionally starts from two materially different candidate identities:

- a GitHub pull request bound to an exact repository, PR number, and head object ID;
- a local artifact bundle bound to a file locator and SHA-256 content digest.

The test in `tests/test_candidate_normalization_equivalence.py` sends both through the same C6-E ResultManifest builder and C6-F verification-handoff boundary.

The acceptance claim is **semantic equivalence**, not byte equality. Candidate-specific identity and worker provenance are allowed to differ. The following must be the same:

- ResultManifest top-level contract shape;
- normalized candidate-reference artifact schema/media type;
- WorkUnit/source provenance;
- verification-request structure and required validator coverage;
- normalization profile;
- verification-handoff structure;
- EvaluatorPlan binding requirements;
- independence/minimum-verifier policy;
- absence of verification, acceptance, merge, and integration authority.

This fixture does not execute a coding agent, verifier, or merge. It proves the provider-erasure boundary only.
