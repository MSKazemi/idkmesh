# PyPI Trusted Publishing and Release Runbook

**Status:** repository automation is implemented; first public PyPI publication
still requires the one-time maintainer setup tracked in issue #769.

This runbook covers the installable `idkmesh` Python package only. It does not
turn the wider research repository or the unfinished Verified Swarm Runner into
a released product.

## Security model

IDKMesh uses PyPI Trusted Publishing rather than a stored API token.

The publication boundary is:

```text
reviewed repository revision
  -> version/tag preflight
  -> build sdist + wheel
  -> twine metadata check
  -> retained GitHub Actions artifact
  -> protected GitHub environment approval
  -> short-lived GitHub OIDC identity
  -> PyPI Trusted Publisher
  -> public package
```

Do not add a PyPI password or long-lived API token to repository secrets.

The publishing workflow is `.github/workflows/publish-pypi.yml`. The OIDC
identity is scoped to:

- GitHub owner: `MSKazemi`
- repository: `idkmesh`
- workflow: `publish-pypi.yml`
- environment: `pypi`

## One-time activation

### 1. Configure the pending publisher on PyPI

On PyPI, create a pending Trusted Publisher for the project name `idkmesh`
with exactly the owner/repository/workflow/environment values above.

A pending publisher is appropriate for the first release because the project
does not need to exist on PyPI beforehand.

### 2. Configure the GitHub environment

Create or verify the repository environment named `pypi`.

Require a deliberate maintainer approval before deployment. The environment is
the human authority gate between a successfully built artifact and a public
package publication.

Do not grant ordinary worker/agent jobs authority to approve that environment.

## Release identity contract

The package version currently has two repository sources:

- `pyproject.toml` -> `project.version`
- `idkmesh/__init__.py` -> `__version__`

`tools/check_release_version.py` requires both values to agree and requires the
release tag to encode the same version. It accepts either `0.1.0` or
`v0.1.0` style tags.

Examples:

```bash
python tools/check_release_version.py --tag v0.1.0
python tools/check_release_version.py --tag refs/tags/v0.1.0
```

A mismatch is a hard failure before the distribution build.

## Preparing a release

1. choose the release version using normal semantic/PEP 440 versioning;
2. update `project.version` in `pyproject.toml`;
3. update `idkmesh.__version__` to the same value;
4. run the focused release test:

   ```bash
   python -m pytest -q tests/test_release_version.py
   ```

5. run the normal PR Gate and package/action self-tests;
6. merge the reviewed version change to protected `main`;
7. create a tag matching that version, preferably `v<version>`;
8. create/publish the GitHub Release from that tag.

Do not create the public GitHub Release until the version bump revision is on
protected `main`.

## What the workflow does

For a published GitHub Release, the workflow:

1. reads `github.event.release.tag_name`;
2. checks out that exact tag rather than whichever branch is current;
3. runs `tools/check_release_version.py` against the tag;
4. installs `build` and `twine`;
5. builds both source and wheel distributions;
6. runs `twine check dist/*`;
7. retains `dist/*` as the `python-distributions` Actions artifact;
8. waits at the protected `pypi` environment;
9. after human approval, requests a short-lived OIDC identity and publishes
   through `pypa/gh-action-pypi-publish`.

Manual dispatch is also supported, but requires an explicit existing release
tag and checks out that tag. It is not a "publish the current branch" escape
hatch.

## First-release acceptance

After publication, verify from clean environments rather than from the
repository checkout.

Python 3.11:

```bash
python3.11 -m venv /tmp/idkmesh-py311
/tmp/idkmesh-py311/bin/python -m pip install --upgrade pip
/tmp/idkmesh-py311/bin/python -m pip install idkmesh
/tmp/idkmesh-py311/bin/idkmesh --version
```

Repeat with Python 3.13.

Then verify the installed CLI against a copied fixture or a fresh clone:

```bash
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

Record:

- the PyPI project URL;
- the exact release tag and commit;
- the publish workflow run;
- whether Trusted Publishing/OIDC was used;
- clean-install evidence for Python 3.11 and 3.13.

Issue #769 is the activation tracker.

## Failure and recovery

### Version/tag mismatch

Do not bypass the preflight. Correct the version or create the right tag, then
publish a new release event from the correct immutable revision.

### Build or Twine failure

No publish should occur. Fix the package/metadata on a reviewed revision and
create the appropriate new tag/version. Do not replace the contents of a
published version.

### OIDC / Trusted Publisher failure

Check the four identity fields: owner, repository, workflow filename, and
environment name. Do not work around an OIDC configuration failure by adding a
long-lived token.

### Bad public release

Prefer releasing a corrected new version. If a release is dangerous or
fundamentally unusable, use PyPI's supported yank/removal controls according to
PyPI policy and document the reason. Do not silently reuse the same version
number with different bytes.

## Evidence boundary

A successful PyPI publication proves that a specific package artifact was built
from the tagged repository revision and accepted by the package index. It does
not prove production readiness, user adoption, research validity, search
ranking, or answer-engine citation.

Those visibility outcomes remain tracked separately in issue #665 and
`evidence/search-visibility/`.
