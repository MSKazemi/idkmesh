# GitHub Bootstrap Safe Local Apply v0.1

**Status:** experimental implementation, C8-F of #596. POSIX-only, local repository writes. No network, GitHub API, secret-value access, provider dispatch, verification, approval, push, or merge.

## Usage

From the root of an initialized Git repository, use a pinned IDKMesh release or a full lowercase commit SHA:

```sh
idkmesh init --github --dry-run --idkmesh-ref v0.1.0
idkmesh init --github --idkmesh-ref v0.1.0 --apply
```

By default the current directory is the target. `--target DIR` (valid with `--check` or `--apply` only; rejected with `--dry-run`) installs into another checkout: `DIR` must exist, must not itself be a symlink, and must contain a `.git` marker, otherwise the run refuses with `invalid_root` or `git_repository_required` and writes nothing. The generated paths are fixed by the canonical plan and never derived from `DIR`. There is intentionally no `--force`: a pre-existing file that is not a previously generated, unmodified managed file is reported (`untracked_managed_file`, `managed_file_modified`) and never overwritten.

The first command is a pure renderer. To inspect real target-file conflicts without modifying the repository, use `--check` instead of `--apply`. `--apply` explicitly opts in to local installation; the command never edits GitHub repository settings. `--json` emits a bounded, deterministic action report.

C8-F uses the canonical C8-A/C/D eight-file inventory: two `user_seed` files (`project.json`, `connections.json`) and six `idkmesh_managed` files. User seeds are **create-if-absent**, never overwritten on rerun. Managed files may change only if their on-disk SHA-256 equals their previously retained generated digest.

The generated `.idkmesh/bootstrap-state.json` stores the six last-rendered managed-file digests and plan metadata; a self-digest detects accidental corruption but does **not** authenticate state against a malicious same-user writer. Commit this state alongside generated files. Its identity is deliberately outside the eight application files.

## Refusal and recovery

- Missing/invalid state with a foreign managed file: refuse, never guess ownership.
- Modified or deleted managed file with existing state: refuse all proposed writes at preflight.
- Symlink or non-regular generated target, symlinked parent, unsafe pathname, non-Git directory, unsupported POSIX directory-relative API: refuse.
- A new release/ref changes only unedited managed files; seeds stay owned by the user.
- C8-F checks all paths before writing, uses directory-relative no-follow operations, exclusive creation of missing files and a temporary file plus rename for replacements. **Multi-file upgrades are not atomic**, and two concurrent writers are not supported. If interrupted, the state written last will normally cause the next run to refuse partial upgrades: inspect and manually reconcile from Git history. Always review `git diff` and keep the branch protected.

The canonical bootstrap renderer validates metadata and SHA-256 digests before local writes; no untrusted external workflow is executed by bootstrap. Rendered GitHub workflow `dispatch` and `verify` runner phases still fail closed; owner setup and external-project validation are separate remaining work.

## Testing

`python -m pytest -q tests/test_github_bootstrap_apply.py` checks first install, no-op replay, changed seed preservation, managed-file conflict refusal, reference upgrade, state corruption and symlink refusal.
