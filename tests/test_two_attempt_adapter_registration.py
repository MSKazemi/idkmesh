"""Result-only worker-adapter registration seam of the two-attempt orchestrator.

Covers v0.1 acceptance criterion 12 ("a newcomer can add a trivial worker
adapter without editing coordinator internals", refs #4, #16). The toy adapters
below live only in this file: nothing in ``experiments/`` is edited to use them.

Every test is in-process (no subprocess) and restores the registry, so the
suite order cannot leak a registered adapter into another test. The tests are
``unittest.TestCase`` methods on purpose: module-level ``test_*`` functions and
parametrization are counted by ``tests/test_documented_test_counts.py``.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

if importlib.util.find_spec("jsonschema") is None:
    raise unittest.SkipTest(
        "adapter registration tests run the real verifier, which needs jsonschema"
    )

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import replay_run  # noqa: E402
import run_evidence_report  # noqa: E402
import two_attempt_orchestrator as orch  # noqa: E402
from provenance_integrity import canonical_digest  # noqa: E402

SCRATCH_ROOT = ROOT / "results" / ".pytest-adapter-registration-scratch"
BUILTIN_CONFIG = ROOT / "examples/orchestration/two-attempt-good-vs-bad.json"
BUILTIN_NAMES = {"fixture-result", "result-bundle", "fixture-failure"}


class ToyBundleDirAdapter:
    """Derives both locations from one `bundle_dir` key (no result_manifest key)."""

    name = "toy-bundle-dir"

    def collect(self, spec: dict[str, Any]) -> orch.CollectedCandidate:
        bundle = spec.get("bundle_dir")
        if not isinstance(bundle, str):
            raise orch.WorkerAttemptError("toy-bundle-dir requires bundle_dir")
        return orch.CollectedCandidate(
            result_manifest_path=orch.resolve_repo_path(f"{bundle}/result-manifest.json"),
            candidate_root=orch.resolve_repo_path(f"{bundle}/candidate-root"),
        )


class ToyMirrorAdapter:
    """Returns exactly the locations named by the spec's own keys."""

    name = "toy-mirror"

    def collect(self, spec: dict[str, Any]) -> orch.CollectedCandidate:
        return orch.CollectedCandidate(
            result_manifest_path=orch.resolve_repo_path(spec["result_manifest"]),
            candidate_root=orch.resolve_repo_path(spec["candidate_root"]),
        )


def toy_config() -> dict[str, Any]:
    base = json.loads(BUILTIN_CONFIG.read_text(encoding="utf-8"))
    base["run_id"] = "orchestration/toy-adapter-registration"
    base["attempts"] = [
        {
            "attempt_id": "attempt-001",
            "worker_adapter": "toy-bundle-dir",
            "bundle_dir": "examples/verifier/good",
        },
        {
            "attempt_id": "attempt-002",
            "worker_adapter": "toy-mirror",
            "result_manifest": "examples/verifier/bad/result-manifest.json",
            "candidate_root": "examples/verifier/bad/candidate-root",
        },
    ]
    return base


class AdapterRegistrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        orch.reset_registered_adapters()
        self.addCleanup(orch.reset_registered_adapters)

    def register_toys(self) -> None:
        orch.register_adapter(ToyBundleDirAdapter.name, ToyBundleDirAdapter())
        orch.register_adapter(ToyMirrorAdapter.name, ToyMirrorAdapter())

    def scratch(self) -> Path:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(dir=SCRATCH_ROOT))

        def cleanup() -> None:
            shutil.rmtree(path, ignore_errors=True)
            try:
                SCRATCH_ROOT.rmdir()
            except OSError:
                pass

        self.addCleanup(cleanup)
        return path

    def write_config(self, directory: Path, config: dict[str, Any]) -> Path:
        path = directory / "config.json"
        path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


class EndToEndTests(AdapterRegistrationTestCase):
    def test_registered_adapter_runs_through_verification_and_report(self) -> None:
        self.register_toys()
        record = orch.orchestrate(toy_config())

        self.assertEqual(record["run_state"], "completed")
        self.assertEqual(
            [a["worker_adapter"] for a in record["attempts"]], ["toy-bundle-dir", "toy-mirror"]
        )
        self.assertEqual([a["state"] for a in record["attempts"]], ["verified", "verified"])
        self.assertEqual(record["summary"]["candidates_supported"], 1)
        self.assertEqual(record["summary"]["candidates_rejected"], 1)

        # The independent verifier saw exactly what the built-in adapters produce.
        builtin = orch.run_config(BUILTIN_CONFIG)
        for toy, ref in zip(record["attempts"], builtin["attempts"]):
            for key in ("state", "candidate_root", "result_manifest", "verification"):
                self.assertEqual(toy[key], ref[key], key)

        report = run_evidence_report.build_report(record)
        run_evidence_report.validate_report(report)
        self.assertEqual(
            [a["worker_adapter"] for a in report["attempts"]], ["toy-bundle-dir", "toy-mirror"]
        )

    def test_registered_run_is_deterministic(self) -> None:
        self.register_toys()
        first = orch.orchestrate(toy_config())
        second = orch.orchestrate(toy_config())
        self.assertEqual(canonical_digest(first), canonical_digest(second))

    def test_registered_adapter_replays_to_the_same_digest(self) -> None:
        self.register_toys()
        scratch = self.scratch()
        config_path = self.write_config(scratch, toy_config())
        manifest = replay_run.capture_bundle(config_path, scratch / "bundle")

        # attempt-001 has no result_manifest/candidate_root keys, so replay's raw
        # sidecar (which reads those keys, not the adapter) is skipped for it.
        self.assertIsNone(manifest["verification_results"]["attempt-001"])
        self.assertIsNotNone(manifest["verification_results"]["attempt-002"])

        report = replay_run.replay_bundle(scratch / "bundle" / "replay-source.json")
        self.assertTrue(report.ok, replay_run.format_report(report))
        self.assertEqual(
            {c.label for c in report.comparisons},
            {"run-record", "evidence-report", "verification-result[attempt-002]"},
        )
        saved = json.loads((scratch / "bundle" / "run-record.json").read_text(encoding="utf-8"))
        self.assertEqual(canonical_digest(saved), canonical_digest(orch.run_config(config_path)))

    def test_replay_fails_closed_when_adapter_is_not_registered(self) -> None:
        """Run records keep only the adapter *name*; they do not embed the adapter.

        Replay re-runs the saved config, so an unregistered name is refused by
        validate_config rather than silently falling back to something else.
        """

        self.register_toys()
        scratch = self.scratch()
        config_path = self.write_config(scratch, toy_config())
        replay_run.capture_bundle(config_path, scratch / "bundle")
        source = scratch / "bundle" / "replay-source.json"

        orch.unregister_adapter("toy-mirror")
        with self.assertRaisesRegex(
            orch.OrchestratorError, "unsupported worker_adapter 'toy-mirror'"
        ):
            replay_run.replay_bundle(source)

        orch.register_adapter(ToyMirrorAdapter.name, ToyMirrorAdapter())
        self.assertTrue(replay_run.replay_bundle(source).ok)

    def test_config_naming_an_unregistered_adapter_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            orch.OrchestratorError, "unsupported worker_adapter 'toy-bundle-dir'"
        ):
            orch.orchestrate(toy_config())

    def test_builtin_only_registry_state_by_default(self) -> None:
        self.assertEqual(set(orch.ADAPTERS), BUILTIN_NAMES)
        self.assertEqual(orch.run_config(BUILTIN_CONFIG)["run_state"], "completed")


class RegistrationRuleTests(AdapterRegistrationTestCase):
    def test_builtin_names_cannot_be_overridden(self) -> None:
        self.assertEqual(set(orch.BUILTIN_ADAPTER_NAMES), BUILTIN_NAMES)
        for name in sorted(BUILTIN_NAMES):
            with self.subTest(name=name):
                original = orch.ADAPTERS[name]

                class Impostor:
                    def collect(self, spec: dict[str, Any]) -> orch.CollectedCandidate:
                        raise orch.WorkerAttemptError("impostor")

                Impostor.name = name  # type: ignore[attr-defined]
                with self.assertRaisesRegex(ValueError, "built-in adapters cannot be overridden"):
                    orch.register_adapter(name, Impostor())
                self.assertIs(orch.ADAPTERS[name], original)

    def test_builtin_adapters_cannot_be_unregistered(self) -> None:
        for name in sorted(BUILTIN_NAMES):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "cannot be unregistered"):
                    orch.unregister_adapter(name)
                self.assertIn(name, orch.ADAPTERS)

    def test_duplicate_registration_is_rejected(self) -> None:
        first = ToyMirrorAdapter()
        orch.register_adapter("toy-mirror", first)
        with self.assertRaisesRegex(ValueError, "already registered"):
            orch.register_adapter("toy-mirror", ToyMirrorAdapter())
        self.assertIs(orch.ADAPTERS["toy-mirror"], first)

    def test_invalid_names_are_rejected(self) -> None:
        names: list[Any] = [
            "", "Toy", "toy_adapter", "toy adapter", "-toy", "toy-", "toy--x", "1toy",
            "toy.x", "toy/x", "../x", "toy\n", "ünï", "a" * 65, None, 7, b"toy",
        ]
        for name in names:
            with self.subTest(name=name):

                class Anything:
                    def collect(self, spec: dict[str, Any]) -> orch.CollectedCandidate:
                        raise orch.WorkerAttemptError("unused")

                adapter = Anything()
                adapter.name = name  # type: ignore[attr-defined]
                with self.assertRaisesRegex(ValueError, "invalid_adapter_name"):
                    orch.register_adapter(name, adapter)
                self.assertEqual(set(orch.ADAPTERS), BUILTIN_NAMES)

    def test_valid_boundary_names_are_accepted(self) -> None:
        for name in ("a", "a1", "toy-adapter-2", "a" * 64):
            with self.subTest(name=name):
                adapter = ToyMirrorAdapter()
                adapter.name = name  # type: ignore[misc]
                orch.register_adapter(name, adapter)
                self.assertIs(orch.ADAPTERS[name], adapter)

    def test_malformed_adapters_are_rejected(self) -> None:
        class NoCollect:
            name = "toy-no-collect"

        class Misnamed(ToyMirrorAdapter):
            name = "toy-other"

        with self.assertRaisesRegex(ValueError, "must implement collect"):
            orch.register_adapter("toy-no-collect", NoCollect())
        with self.assertRaisesRegex(ValueError, "adapter.name must equal"):
            orch.register_adapter("toy-mirror", Misnamed())
        with self.assertRaisesRegex(ValueError, "instance, not a class"):
            orch.register_adapter("toy-mirror", ToyMirrorAdapter)
        self.assertEqual(set(orch.ADAPTERS), BUILTIN_NAMES)

    def test_unregister_and_reset(self) -> None:
        self.register_toys()
        orch.unregister_adapter("toy-mirror")
        self.assertNotIn("toy-mirror", orch.ADAPTERS)
        with self.assertRaisesRegex(ValueError, "not registered"):
            orch.unregister_adapter("toy-mirror")
        orch.reset_registered_adapters()
        self.assertEqual(set(orch.ADAPTERS), BUILTIN_NAMES)


class ContractTests(AdapterRegistrationTestCase):
    def test_contract_declares_no_authority_execution_or_network(self) -> None:
        authority = orch.ADAPTER_CONTRACT["authority"]
        self.assertEqual(
            dict(authority),
            {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
                "command_execution": False,
                "network_access": False,
            },
        )
        with self.assertRaises(TypeError):
            authority["merge"] = True  # type: ignore[index]
        with self.assertRaises(TypeError):
            orch.ADAPTER_CONTRACT["authority"] = {}  # type: ignore[index]
        self.assertIn("CollectedCandidate", orch.ADAPTER_CONTRACT["returns"])

    def test_registered_runs_carry_the_fixed_no_authority_block(self) -> None:
        self.register_toys()
        record = orch.orchestrate(toy_config())
        self.assertEqual(
            record["authority"],
            {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
        )
        # The record's own authority keys are the contract's non-execution subset.
        for key, value in record["authority"].items():
            self.assertIs(orch.ADAPTER_CONTRACT["authority"][key], value)

    def test_adapter_returning_a_non_candidate_is_an_isolated_worker_error(self) -> None:
        class ReturnsDict:
            name = "toy-returns-dict"

            def collect(self, spec: dict[str, Any]) -> Any:
                return {"result_manifest": spec["result_manifest"]}

        self.register_toys()
        orch.register_adapter("toy-returns-dict", ReturnsDict())
        config = toy_config()
        config["attempts"][0] = {
            "attempt_id": "attempt-001",
            "worker_adapter": "toy-returns-dict",
            "result_manifest": "examples/verifier/good/result-manifest.json",
        }
        record = orch.orchestrate(config)
        broken, peer = record["attempts"]
        self.assertEqual(broken["state"], "worker_error")
        self.assertIn("not CollectedCandidate", broken["error"])
        self.assertEqual(peer["state"], "verified")
        self.assertEqual(record["run_state"], "completed_with_failures")

    def test_adapter_cannot_mutate_the_config_it_is_digested_from(self) -> None:
        class Mutating:
            name = "toy-mutating"

            def collect(self, spec: dict[str, Any]) -> orch.CollectedCandidate:
                spec["injected"] = "should not reach config_digest"
                spec["result_manifest"] = "examples/verifier/bad/result-manifest.json"
                return orch.CollectedCandidate(
                    orch.resolve_repo_path("examples/verifier/good/result-manifest.json"),
                    orch.resolve_repo_path("examples/verifier/good/candidate-root"),
                )

        orch.register_adapter("toy-mutating", Mutating())
        config = toy_config()
        config["attempts"][0] = {
            "attempt_id": "attempt-001",
            "worker_adapter": "toy-mutating",
            "result_manifest": "examples/verifier/good/result-manifest.json",
            "candidate_root": "examples/verifier/good/candidate-root",
        }
        config["attempts"][1] = {
            "attempt_id": "attempt-002",
            "worker_adapter": "fixture-result",
            "result_manifest": "examples/verifier/bad/result-manifest.json",
            "candidate_root": "examples/verifier/bad/candidate-root",
        }
        before = json.dumps(config, sort_keys=True)
        record = orch.orchestrate(config)
        self.assertEqual(json.dumps(config, sort_keys=True), before)
        self.assertEqual(record["config_digest"], canonical_digest(json.loads(before)))


if __name__ == "__main__":
    unittest.main()
