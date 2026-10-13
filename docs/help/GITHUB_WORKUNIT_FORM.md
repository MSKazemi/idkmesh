# GitHub WorkUnit request — no-JSON walkthrough

**Status:** experimental, offline/read-only preview. **Issue:** [#608](https://github.com/MSKazemi/idkmesh/issues/608), C13-H.

IDKMesh accepts a structured GitHub Issue Form so contributors can describe bounded work without writing a WorkUnit JSON file. **An issue is a proposal, not authorization.** Human/project policy determines what the preview can describe; no issue form author can grant a worker secrets, network rights, executable checks, dispatch, verification, or merge authority.

## Step 1 — propose work in GitHub

Open the repository's [new-issue chooser](https://github.com/MSKazemi/idkmesh/issues/new/choose) and select **IDKMesh WorkUnit request**. Fill in the Objective, Task class, Expected outputs, Requested allowed paths, Forbidden or sensitive paths, Dependencies or blockers, Acceptance checks, Risk hint, Data sensitivity, External processing hint, Human review requirement, and optional Preferred connector. Tick the safety acknowledgement. Do not paste credentials or confidential data into a public issue.

Example: ask to clarify `docs/BEGINNER_GUIDE.md`, request that file under Allowed paths, list a deterministic test as an acceptance check, and require human review. The requested paths may only *narrow* the trusted repository policy. A selected connector is only a preference; a check written in the issue is never automatically executed as a validator.

## Step 2 — run the committed example without GitHub access

From the **repository root**, with Python 3.11+ and the package available in this checkout (for example, `python -m pip install -e .` in a virtual environment), run on Linux/macOS:

```bash
python -m idkmesh.cli work preview \
  --issue-json examples/github-workunit-intake/issue-valid.json \
  --project-root examples/github-workunit-intake/project \
  --repository MSKazemi/idkmesh \
  --source-revision "$(git rev-parse HEAD)" \
  --json
```

The saved issue is deliberately **synthetic** (issue #424242 is not an observed GitHub issue); `--source-revision` must be an **exact trusted Git SHA**. The shell example resolves the current checkout's actual HEAD. On PowerShell, obtain it with `git rev-parse HEAD` and pass the resulting SHA to `--source-revision`.

A valid result reports `preview.intake.status = "parsed"`, `dispatch_performed = false`, `github_mutation_performed = false`, `secret_values_accessed = false`, the WorkUnit digest and policy-bounded scopes. The form asks for documentation work but the trusted preview policy still supplies WorkUnit `kind = coding`. Its `high` risk hint **raises** the medium trusted baseline. This is a diagnostic preview, not high-risk execution approval. Form-level `external processing: forbidden` becomes a restrictive policy tag; actual egress is controlled separately by trusted permissions/admission.

The trusted test policy is at [`project/.idkmesh/project.json`](../../examples/github-workunit-intake/project/.idkmesh/project.json). It explicitly limits paths to `docs/**` and `tests/**` and keeps `SECURITY.md`, `.github/**`, and `.idkmesh/**` excluded. It does not contain provider secrets.

## Step 3 — compare fallback and refusal

For an **unchecked safety acknowledgement**, the Issue Form cannot be parsed confidently. Try:

```bash
python -m idkmesh.cli work preview \
  --issue-json examples/github-workunit-intake/issue-unchecked.json \
  --project-root examples/github-workunit-intake/project \
  --repository MSKazemi/idkmesh \
  --source-revision "$(git rev-parse HEAD)" --json
```

This produces `preview.intake.status = "fallback"` and the **generic policy-owned** WorkUnit, not a form-restricted WorkUnit. Its paths are the trusted policy paths, so do **not** treat a fallback as proof that the requester's constraints were adopted. Fix and resubmit the issue for a structured preview.

For a **well-formed** issue that requests only `.github/workflows/ci.yml` outside the trusted scope, substitute `issue-out-of-scope.json` for `--issue-json`; the command refuses with `error: policy_denied` and exit code **2**. An out-of-scope path never becomes a new permission.

For human-readable output, omit `--json`. The text mode omits raw issue title/body and prints identifiers, digest, effective scopes and warnings only. JSON output includes untrusted task content; review/redact it before sharing.

## Step 4 — use your own issue

A maintainer can obtain the GitHub REST issue JSON separately (for a public issue, from `https://api.github.com/repos/OWNER/REPO/issues/NUMBER`) and pass the saved local response to `--issue-json`. `idkmesh work preview` **does not fetch it** and does not edit the repository. A trusted `.idkmesh/project.json` must already declare `metadata.github_issue_preview.allowed_paths`; `idkmesh init --github --dry-run` can render example policy templates but does not apply files or change GitHub settings.

## Validation and scope

Run `python -m pytest -q tests/test_github_workunit_no_json_example.py` for the committed examples. For other installation issues, see [troubleshooting](TROUBLESHOOTING.md); for the field rules and preview semantics, see the [intake specification](../specifications/GITHUB_WORKUNIT_INTAKE_V0_1.md).

This demonstrates only the current **offline parser/preview** boundary. It is not a hosted onboarding wizard, GitHub Projects sync, autonomous agent dispatcher, security sandbox, or human decision API. `#804` still owns sandbox enforcement.
