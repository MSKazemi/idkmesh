import copy
import unittest

from experiments import project_contracts as MODULE


class ProjectDomainContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.self_project = MODULE.load_json(
            MODULE.resolve_repo_path(
                "examples/projects/idkmesh-self-improvement.project.json"
            )
        )

    def test_two_distinct_projects_load_on_same_core_contract(self):
        projects = MODULE.validate_repository_contracts()
        self.assertEqual(len(projects), 2)
        self.assertNotEqual(projects[0]["id"], projects[1]["id"])
        self.assertEqual(
            projects[0]["core_compatibility"],
            projects[1]["core_compatibility"],
        )
        self.assertNotEqual(
            projects[0]["allowed_work_unit_kinds"],
            projects[1]["allowed_work_unit_kinds"],
        )

    def test_project_cannot_enable_unsupported_work_unit_kind(self):
        project = copy.deepcopy(self.self_project)
        project["allowed_work_unit_kinds"].append("governance")
        with self.assertRaisesRegex(MODULE.ProjectContractError, "not supplied"):
            MODULE.validate_project(project)

    def test_project_cannot_omit_required_adapter(self):
        project = copy.deepcopy(self.self_project)
        project["enabled_adapters"].remove("software.metadata-verifier")
        with self.assertRaisesRegex(MODULE.ProjectContractError, "required adapter"):
            MODULE.validate_project(project)

    def test_project_cannot_weaken_independent_verifier_requirement(self):
        project = copy.deepcopy(self.self_project)
        project["verification"]["minimum_independent_verifiers"] = 0
        with self.assertRaisesRegex(MODULE.ProjectContractError, "minimum independent verifiers"):
            MODULE.validate_project(project)

    def test_project_cannot_silently_rebind_domain_pack_version(self):
        project = copy.deepcopy(self.self_project)
        project["domain_packs"][0]["version"] = "0.2.0"
        with self.assertRaisesRegex(MODULE.ProjectContractError, "version mismatch"):
            MODULE.validate_project(project)

    def test_project_cannot_escape_repository_for_domain_pack(self):
        project = copy.deepcopy(self.self_project)
        project["domain_packs"][0]["path"] = "../../etc/passwd"
        with self.assertRaisesRegex(MODULE.ProjectContractError, "escapes repository root"):
            MODULE.validate_project(project)

    def test_exact_core_compatibility_fails_closed(self):
        project = copy.deepcopy(self.self_project)
        project["core_compatibility"]["core_api_version"] = "9.9"
        with self.assertRaisesRegex(MODULE.ProjectContractError, "unsupported Core API"):
            MODULE.validate_project(project)

    def test_self_test_contract(self):
        MODULE.self_test()


if __name__ == "__main__":
    unittest.main()
