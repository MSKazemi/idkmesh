"""Guard the per-metric contract page against rot in both directions.

`docs/research/METRIC_CONTRACTS_V0_1.md` documents, for every production metric,
the seven fields issue #86 requires: assumptions, observables, uncertainty,
prediction, baseline, failure modes, and human/security constraints.

The metric keys are read out of the code by AST rather than hand-listed, so a
metric added to the code without a contract fails here, and a contract kept for
a metric the code no longer emits fails here too. The collaboration keys are
additionally cross-checked against what `analyze` really emits for a frozen
fixture, so the AST view cannot drift away from the runtime view.

This guard checks that each field exists and is non-empty. It cannot check that
the prose is true; that stays a review duty.

Only the standard library is imported: CI installs jsonschema and pytest only.

The checks are `unittest.TestCase` methods on purpose. `tests/test_documented_test_counts.py`
publishes the number of module-level `test_*` functions in three places; a class keeps this
guard out of that count so adding it does not force a three-way documentation edit.
"""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/METRIC_CONTRACTS_V0_1.md"
SCORE = ROOT / "scripts/repository_evolution_score.py"
GOVERNOR = ROOT / "scripts/evolution_live_governor.py"
OBSERVABLES = ROOT / "scripts/collaboration_observables.py"
FIXTURE = ROOT / "tests/fixtures/collaboration_observables_snapshot.json"

FIELDS = (
    "Assumptions",
    "Observables",
    "Uncertainty",
    "Prediction",
    "Baseline",
    "Failure modes / Goodhart risks",
    "Human / security constraints",
)

# A field must say something. Twenty characters excludes "TBD", "n/a", "None."
# and an empty bullet while still allowing a short honest sentence.
MINIMUM_FIELD_LENGTH = 20
PLACEHOLDER = re.compile(r"^(tbd|todo|n/?a|none|\.\.\.|-)\.?$", re.IGNORECASE)

ENTRY_HEADING = re.compile(r"^### `([^`]+)`\s*$", re.MULTILINE)
ANY_HEADING = re.compile(r"^#{1,3} ", re.MULTILINE)
FIELD_BULLET = re.compile(
    r"^- \*\*(?P<label>[^*]+?):\*\*(?P<body>.*?)(?=^- \*\*|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Composite mechanisms are not signals, so no single return dict lists them.
# Each is a (file, function, key) triple that must exist in that function's
# literal return dict; the key is then required to have a contract.
COMPOSITES = (
    (SCORE, "evaluate", "control_energy_proxy"),
    (SCORE, "evaluate", "strategy_weights"),
    (SCORE, "_scored", "priority"),
    (GOVERNOR, "evaluate", "homeostatic_potential"),
)


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1, f"expected exactly one {name} in {path.name}, found {len(matches)}"
    return matches[0]


def _return_dict(path: Path, name: str) -> ast.Dict:
    """The literal dict returned by the function, found by AST."""
    returned = [
        node.value
        for node in ast.walk(_function(path, name))
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
    ]
    assert len(returned) == 1, f"{name} in {path.name} must return exactly one dict literal"
    return returned[0]


def _string_keys(node: ast.Dict) -> list[str]:
    keys: list[str] = []
    for key in node.keys:
        # A `**spread` has key None; a computed key is not a constant string.
        assert isinstance(key, ast.Constant) and isinstance(key.value, str), (
            "metric dictionaries must use literal string keys so the guard can read them"
        )
        keys.append(key.value)
    return keys


def _dict_value(node: ast.Dict, key: str) -> ast.expr:
    for candidate, value in zip(node.keys, node.values):
        if isinstance(candidate, ast.Constant) and candidate.value == key:
            return value
    raise AssertionError(f"key {key!r} not found")


def _collaboration_metric_keys() -> list[str]:
    result = _return_dict(OBSERVABLES, "analyze")
    metrics = _dict_value(result, "metrics")
    assert isinstance(metrics, ast.Dict), "analyze must return a literal metrics dict"
    return _string_keys(metrics)


def code_metrics() -> dict[str, str]:
    """Every metric key the code produces, mapped to a provenance note."""
    found: dict[str, str] = {}

    def add(keys: list[str], origin: str) -> None:
        for key in keys:
            found.setdefault(key, origin)

    add(_string_keys(_return_dict(SCORE, "normalized_signals")), "score normalized_signals")
    add(_string_keys(_return_dict(GOVERNOR, "live_signals")), "governor live_signals")
    add(_collaboration_metric_keys(), "collaboration analyze metrics")
    analyze_keys = _string_keys(_return_dict(OBSERVABLES, "analyze"))
    assert "evidence_derived_strategy_priors" in analyze_keys
    add(["evidence_derived_strategy_priors"], "collaboration analyze top level")
    for path, function, key in COMPOSITES:
        assert key in _string_keys(_return_dict(path, function)), (
            f"{key} is no longer in {function}() of {path.name}; update COMPOSITES and the doc"
        )
        add([key], f"{path.name} {function}")
    return found


def doc_entries() -> dict[str, str]:
    """Entry name -> entry body, from the `###` headings in the contract page."""
    text = DOC.read_text(encoding="utf-8")
    entries: dict[str, str] = {}
    headings = list(ENTRY_HEADING.finditer(text))
    assert headings, "the contract page has no metric entries"
    for match in headings:
        name = match.group(1)
        assert name not in entries, f"duplicate contract entry: {name}"
        following = ANY_HEADING.search(text, match.end())
        end = following.start() if following else len(text)
        entries[name] = text[match.end():end]
    return entries


def entry_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in FIELD_BULLET.finditer(body):
        label = match.group("label").strip()
        assert label not in fields, f"duplicate field {label!r}"
        fields[label] = " ".join(match.group("body").split())
    return fields


class MetricContractTests(unittest.TestCase):
    def test_every_code_metric_has_a_contract_entry(self) -> None:
        missing = sorted(set(code_metrics()) - set(doc_entries()))
        self.assertFalse(
            missing,
            "metrics emitted by the code have no entry in "
            f"docs/research/METRIC_CONTRACTS_V0_1.md: {missing}",
        )

    def test_every_entry_has_all_seven_non_empty_fields(self) -> None:
        problems: list[str] = []
        for name, body in doc_entries().items():
            fields = entry_fields(body)
            for label in FIELDS:
                value = fields.get(label)
                if value is None:
                    problems.append(f"{name}: missing field {label!r}")
                elif len(value) < MINIMUM_FIELD_LENGTH or PLACEHOLDER.match(value):
                    problems.append(f"{name}: field {label!r} is empty or a placeholder")
            for label in sorted(set(fields) - set(FIELDS)):
                problems.append(f"{name}: unexpected field {label!r}")
        self.assertFalse(problems, "\n".join(problems))

    def test_no_entry_for_a_metric_the_code_no_longer_emits(self) -> None:
        stale = sorted(set(doc_entries()) - set(code_metrics()))
        self.assertFalse(
            stale,
            "contract entries name metrics the code no longer emits "
            f"(remove or rename them): {stale}",
        )

    def test_collaboration_ast_keys_match_what_analyze_emits(self) -> None:
        """The AST view of the analyzer must equal its runtime output."""
        from scripts.collaboration_observables import analyze

        result = analyze(json.loads(FIXTURE.read_text(encoding="utf-8")))
        self.assertEqual(sorted(result["metrics"]), sorted(_collaboration_metric_keys()))
        self.assertIn("evidence_derived_strategy_priors", result)
