"""Deterministic C8-C GitHub bootstrap configuration rendering.

This module consumes the C8-A GitHubBootstrapPlan and renders only the four
configuration files owned by C8-C. It is pure: no filesystem writes, network
calls, GitHub mutations, secret resolution, workflow execution, dispatch,
verification, or integration are performed.

Repeated rendering of the same plan produces byte-identical UTF-8 content and
stable SHA-256 digests. Those digests are intended for the later C8-F safe
re-run/apply boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from idkmesh.github_bootstrap import GitHubBootstrapPlan


CONFIG_PHASE = "C8-C"
_CONFIG_PATHS = frozenset(
    {
        ".idkmesh/README.md",
        ".idkmesh/connections.json",
        ".idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json",
        ".idkmesh/project.json",
    }
)

_DOMAIN_PACK_JSON = r"""
{
  "schema_version": "0.1",
  "id": "domain.software-engineering",
  "version": "0.1.0",
  "name": "Software Engineering",
  "description": "Domain rules for bounded repository engineering, testing, review, benchmarking, research, documentation, and protected integration.",
  "core_compatibility": {
    "core_api_version": "0.1",
    "work_unit_schema_version": "0.2"
  },
  "work_unit_kinds": [
    {
      "kind": "coding",
      "default_risk_class": "medium",
      "required_verification_policy": "software.code-change",
      "required_capabilities": ["repository-edit"],
      "required_evidence": ["test_output", "artifact_hash"]
    },
    {
      "kind": "testing",
      "default_risk_class": "low",
      "required_verification_policy": "software.test-change",
      "required_capabilities": ["test-execution"],
      "required_evidence": ["test_output"]
    },
    {
      "kind": "review",
      "default_risk_class": "medium",
      "required_verification_policy": "software.independent-review",
      "required_capabilities": ["repository-read"],
      "required_evidence": ["review"]
    },
    {
      "kind": "benchmarking",
      "default_risk_class": "low",
      "required_verification_policy": "software.benchmark",
      "required_capabilities": ["deterministic-execution"],
      "required_evidence": ["benchmark", "artifact_hash"]
    },
    {
      "kind": "documentation",
      "default_risk_class": "low",
      "required_verification_policy": "software.docs-change",
      "required_capabilities": ["repository-edit"],
      "required_evidence": ["review"]
    },
    {
      "kind": "research",
      "default_risk_class": "low",
      "required_verification_policy": "software.research-evidence",
      "required_capabilities": ["repository-read"],
      "required_evidence": ["citation", "artifact_hash"]
    },
    {
      "kind": "integration",
      "default_risk_class": "high",
      "required_verification_policy": "software.integration",
      "required_capabilities": ["repository-read"],
      "required_evidence": ["review", "test_output", "attestation"]
    }
  ],
  "verification_policies": [
    {
      "id": "software.code-change",
      "strategy": "all_required",
      "independent_from_worker": true,
      "minimum_independent_verifiers": 1,
      "human_integration_required": true,
      "description": "Code changes require deterministic checks plus a verifier independent from the producing worker; integration remains human/governance controlled."
    },
    {
      "id": "software.test-change",
      "strategy": "all_required",
      "independent_from_worker": true,
      "minimum_independent_verifiers": 1,
      "human_integration_required": true
    },
    {
      "id": "software.independent-review",
      "strategy": "all_required",
      "independent_from_worker": true,
      "minimum_independent_verifiers": 1,
      "human_integration_required": true
    },
    {
      "id": "software.benchmark",
      "strategy": "all_required",
      "independent_from_worker": true,
      "minimum_independent_verifiers": 1,
      "human_integration_required": false
    },
    {
      "id": "software.docs-change",
      "strategy": "all_required",
      "independent_from_worker": false,
      "minimum_independent_verifiers": 0,
      "human_integration_required": true
    },
    {
      "id": "software.research-evidence",
      "strategy": "all_required",
      "independent_from_worker": false,
      "minimum_independent_verifiers": 0,
      "human_integration_required": true
    },
    {
      "id": "software.integration",
      "strategy": "all_required",
      "independent_from_worker": true,
      "minimum_independent_verifiers": 1,
      "human_integration_required": true
    }
  ],
  "worker_roles": [
    {
      "id": "software.builder",
      "description": "Produces bounded candidate repository changes.",
      "required_capabilities": ["repository-edit"]
    },
    {
      "id": "software.tester",
      "description": "Runs bounded deterministic tests and reproductions.",
      "required_capabilities": ["test-execution"]
    },
    {
      "id": "software.reviewer",
      "description": "Inspects candidate evidence independently from the producer.",
      "required_capabilities": ["repository-read"]
    },
    {
      "id": "software.benchmarker",
      "description": "Runs replayable benchmark workloads.",
      "required_capabilities": ["deterministic-execution"]
    }
  ],
  "risk_classes": [
    {
      "id": "low",
      "sandbox_required": true,
      "human_review_required": false,
      "description": "Low-impact isolated work with deterministic evidence."
    },
    {
      "id": "medium",
      "sandbox_required": true,
      "human_review_required": true,
      "description": "Repository behavior changes requiring human integration review."
    },
    {
      "id": "high",
      "sandbox_required": true,
      "human_review_required": true,
      "description": "Security, workflow, protocol, evaluator, integration, or governance-sensitive change."
    },
    {
      "id": "critical",
      "sandbox_required": true,
      "human_review_required": true,
      "description": "Authority-bearing or high-consequence change requiring explicit governance."
    }
  ],
  "adapters": {
    "definitions": [
      {
        "id": "software.repository",
        "interface": "idkmesh.adapter.repository/v0.1",
        "discovery": "project-manifest",
        "trust_boundary": "Resolves project-declared repository roots; the manifest does not grant write authority."
      },
      {
        "id": "software.sandbox-worker",
        "interface": "idkmesh.adapter.worker/v0.1",
        "discovery": "registry",
        "trust_boundary": "Worker execution remains disposable/capability-bounded and cannot self-accept output."
      },
      {
        "id": "software.metadata-verifier",
        "interface": "idkmesh.adapter.verifier/v0.1",
        "discovery": "registry",
        "trust_boundary": "Verifier consumes candidate metadata/evidence under verifier-owned policy and has no merge authority."
      }
    ],
    "required": ["software.repository", "software.metadata-verifier"],
    "optional": ["software.sandbox-worker"]
  },
  "metrics": {
    "default": ["verified_useful_output", "verification_latency", "human_minutes", "replay_success"]
  },
  "compatibility": {
    "backward_compatible_with": ["0.1.0"],
    "breaking_change_policy": "Breaking semantics require a new DomainPack major version or schema version and explicit ProjectManifest re-binding; silent downgrade is forbidden."
  }
}
"""


class BootstrapRenderError(ValueError):
    """Fail-closed C8-C rendering error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def _digest(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BootstrapRenderedFile:
    path: str
    ownership: str
    overwrite_policy: str
    render_source: str
    content: str
    content_digest: str
    size_bytes: int

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": self.path,
            "ownership": self.ownership,
            "overwrite_policy": self.overwrite_policy,
            "render_source": self.render_source,
            "content_digest": self.content_digest,
            "size_bytes": self.size_bytes,
            "secret_values_accessed": False,
            "integration_authority": False,
        }
        if include_content:
            result["content"] = self.content
        return result


def _project_document(plan: GitHubBootstrapPlan) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "id": "project.github-bootstrap",
        "version": "0.1.0",
        "name": "IDKMesh GitHub project",
        "description": (
            "Bootstrap seed for a GitHub-first IDKMesh software project. "
            "Customize project identity and goals before dispatch."
        ),
        "core_compatibility": {
            "core_api_version": "0.1",
            "work_unit_schema_version": "0.2",
        },
        "roots": [
            {
                "id": "repository",
                "kind": "repository",
                "uri": ".",
                "writable": True,
            }
        ],
        "goal_entrypoints": ["README.md"],
        "domain_packs": [
            {
                "id": "domain.software-engineering",
                "version": "0.1.0",
                "path": (
                    ".idkmesh/domain-packs/"
                    "software-engineering-v0.1.domain-pack.json"
                ),
            }
        ],
        "allowed_work_unit_kinds": [
            "coding",
            "testing",
            "review",
            "benchmarking",
            "documentation",
            "research",
            "integration",
        ],
        "verification": {
            "default_policy_ref": "software.code-change",
            "minimum_independent_verifiers": 1,
            "human_integration_required": True,
        },
        "risk_policy": {
            "allowed_risk_classes": ["low", "medium", "high"],
            "maximum_autonomous_risk": "low",
        },
        "integration_policy": {
            "mode": "protected_pr",
            "target_branch": plan.default_branch,
            "automatic_merge_allowed": False,
            "human_decision_required": True,
        },
        "governance": {
            "owners": ["role:repository-owner"],
            "reviewers": ["role:independent-reviewer"],
            "decision_refs": [".idkmesh/README.md"],
        },
        "metrics": {
            "primary": "verified_useful_work_per_human_minute",
            "secondary": [
                "verification_latency",
                "replay_success",
                "review_queue_pressure",
            ],
        },
        "worker_constraints": {
            "required_capabilities": ["repository-read"],
            "forbidden_capabilities": [
                "repository-merge-authority",
                "governance-mutation-authority",
            ],
        },
        "storage": {
            "artifact_root": ".idkmesh/evidence/artifacts/",
            "result_root": ".idkmesh/evidence/results/",
            "provenance_root": ".idkmesh/evidence/provenance/",
        },
        "enabled_adapters": [
            "software.repository",
            "software.metadata-verifier",
        ],
        "metadata": {
            "bootstrap_template": True,
            "customize_before_dispatch": True,
            "idkmesh_ref": plan.idkmesh_ref,
            "authority_note": (
                "This generated seed narrows policy but grants no worker, "
                "verifier, approval, merge, or governance authority."
            ),
        },
    }


def _connections_document(plan: GitHubBootstrapPlan) -> list[dict[str, Any]]:
    return [
        {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "jules-main",
            "kind": "agent",
            "driver": "jules",
            "enabled": False,
            "auth": {"secret_ref": "env:JULES_API_KEY"},
            "settings": {
                "source": "sources/github/OWNER/REPOSITORY",
                "starting_branch": plan.default_branch,
                "require_plan_approval": True,
            },
            "capabilities": {
                "tiers": ["T1", "T2"],
                "task_classes": ["coder"],
                "tools": ["git"],
                "candidate_types": ["github_pull_request"],
                "max_risk": "low",
            },
            "policy": {
                "task_classes": ["coder"],
                "allowed_risk": ["low"],
                "external_processing": True,
                "project_spend_usd_max": 0,
                "max_concurrency": 1,
            },
            "independence": {
                "provider_family": "google",
                "agent_family": "jules",
                "execution_family": "jules-hosted",
            },
        }
    ]


def _readme(plan: GitHubBootstrapPlan) -> str:
    return f"""# IDKMesh project bootstrap

This directory was rendered by the C8-C GitHub-first bootstrap contract.

Pinned IDKMesh reference: {plan.idkmesh_ref}
Protected integration branch target: {plan.default_branch}

## Before dispatch

1. Customize project.json project identity, goals, governance roles, and policy.
2. Replace OWNER/REPOSITORY in connections.json with the configured Jules Source.
3. Keep connectors disabled until the owner has configured the corresponding
   provider app and secret reference.
4. Store the JULES_API_KEY value only in GitHub Secrets or another approved
   runtime secret store. Do not write secret values into this directory.
5. Protect the integration branch and keep human/protected integration required.

## Ownership

- project.json and connections.json are user_seed files. Later bootstrap apply
  logic must create them only when absent and must never overwrite user edits.
- this README and the vendored DomainPack are idkmesh_managed. A later safe
  re-run may replace managed files only when the retained generated digest
  proves that the user has not edited the previous generated content.

## Authority

These files configure or narrow project behavior only. This generated
configuration does not grant dispatch, verification acceptance, repository
administration, Git push, or merge authority. Worker success is not acceptance,
and verification recommendation is not integration authority.

C8-C renders bytes and digests only. It performs no filesystem or GitHub
mutation. Workflow wrappers and apply/re-run behavior are separate C8-D/C8-F
slices.
"""


def render_github_bootstrap_config(
    plan: GitHubBootstrapPlan,
) -> tuple[BootstrapRenderedFile, ...]:
    """Render exactly the C8-C entries from a validated bootstrap plan."""

    if not isinstance(plan, GitHubBootstrapPlan):
        raise TypeError("plan must be GitHubBootstrapPlan")

    specs = tuple(item for item in plan.files if item.phase == CONFIG_PHASE)
    paths = {item.path for item in specs}
    if paths != _CONFIG_PATHS:
        missing = sorted(_CONFIG_PATHS - paths)
        extra = sorted(paths - _CONFIG_PATHS)
        raise BootstrapRenderError(
            "config_plan_mismatch",
            f"C8-C file plan mismatch: missing={missing} extra={extra}",
        )

    domain_pack = json.loads(_DOMAIN_PACK_JSON)
    renderers = {
        ".idkmesh/README.md": lambda: _readme(plan),
        ".idkmesh/connections.json": lambda: _json_text(
            _connections_document(plan)
        ),
        ".idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json": (
            lambda: _json_text(domain_pack)
        ),
        ".idkmesh/project.json": lambda: _json_text(_project_document(plan)),
    }

    rendered: list[BootstrapRenderedFile] = []
    for spec in sorted(specs, key=lambda item: item.path):
        renderer = renderers.get(spec.path)
        if renderer is None:
            raise BootstrapRenderError(
                "unknown_render_source",
                f"no C8-C renderer for {spec.path}",
            )
        content = renderer()
        if not isinstance(content, str) or not content.endswith("\n"):
            raise BootstrapRenderError(
                "invalid_rendered_content",
                f"{spec.path}: renderer must return newline-terminated text",
            )
        rendered.append(
            BootstrapRenderedFile(
                path=spec.path,
                ownership=spec.ownership,
                overwrite_policy=spec.overwrite_policy,
                render_source=spec.render_source,
                content=content,
                content_digest=_digest(content),
                size_bytes=len(content.encode("utf-8")),
            )
        )

    return tuple(rendered)
