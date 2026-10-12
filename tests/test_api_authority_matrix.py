"""Guards for docs/specifications/API_AUTHORITY_MATRIX_V0_1.md (issue #743).

The matrix is a proposal for the network profile, but two things in it are
checkable facts and are checked: that it covers exactly the routes the server
serves, and what the server enforces today.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import re
import threading
import unittest
from unittest import mock

from idkmesh.control_tower_ui import TOKEN_ENV, create_server
from idkmesh.enterprise_authz import ACTIONS, ROLES
from idkmesh.local_ui_security import TOKEN_HEADER

DOC = Path(__file__).resolve().parents[1] / "docs" / "specifications" / "API_AUTHORITY_MATRIX_V0_1.md"
TOKEN = "m" * 32
MUTATING = {"dispatch", "execute", "verify", "integrate", "manage_policy", "audit_export", "claim", "release"}
ROW = re.compile(r"^\| `((?:GET|POST) [^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", re.MULTILINE)


def _served_section(text):
    return text.split("## Matrix: endpoints the server serves")[1].split("## Matrix: endpoints that do not exist yet")[0]


class AuthorityMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        with mock.patch.dict(os.environ, {TOKEN_ENV: TOKEN}):
            cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.rows = ROW.findall(_served_section(cls.text))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, *, token=True, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            all_headers = dict(headers or {})
            if token:
                all_headers[TOKEN_HEADER] = TOKEN
            conn.request(method, path, headers=all_headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def discovered(self):
        status, body = self.request("GET", "/api/v1/status")
        self.assertEqual(status, 200)
        return set(json.loads(body)["endpoints"].values())

    def test_the_matrix_covers_exactly_the_routes_the_server_serves(self):
        documented = {row[0] for row in self.rows}
        self.assertEqual(sorted(self.discovered() - documented), [], "served but no authority row")
        self.assertEqual(sorted(documented - self.discovered()), [], "row for a route not served")

    def test_every_action_and_role_named_exists_in_the_kernel(self):
        for endpoint, action, _scope, roles, _floor, _enforced in self.rows:
            action = action.strip().strip("`")
            if action.startswith("none"):
                continue
            with self.subTest(endpoint=endpoint):
                self.assertIn(action, ACTIONS)
                for role in (r.strip() for r in roles.split(",")):
                    if role in ("any", "unauthenticated"):
                        continue
                    self.assertIn(role, ROLES, role)

    def test_no_served_endpoint_needs_a_mutating_authority(self):
        for endpoint, action, *_ in self.rows:
            with self.subTest(endpoint=endpoint):
                self.assertNotIn(action.strip().strip("`"), MUTATING)

    def test_the_unserved_human_decision_route_really_is_not_served(self):
        self.assertIn("POST /api/v1/human-decisions", self.text.split("do not exist yet")[1])
        status, _ = self.request("POST", "/api/v1/human-decisions")
        self.assertEqual(status, 404)

    def test_enforced_today_is_a_session_token_not_a_principal(self):
        for endpoint, _a, _s, _r, _f, enforced in self.rows:
            method, path = endpoint.split(" ", 1)
            concrete = re.sub(r"\{[a-z_]+\}", "x", path)
            if not path.startswith("/api/v1/"):
                self.assertIn("Host check only", enforced)
                continue
            with self.subTest(endpoint=endpoint):
                self.assertIn("session token", enforced)
                status, body = self.request(method, concrete, token=False)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(body)["error"]["code"], "invalid_session_token")

    def test_a_principal_header_changes_nothing(self):
        # No endpoint accepts a principal today: claiming a role is just a header.
        base = self.request("GET", "/api/v1/status")
        for header in ("X-IDKMesh-Role", "X-IDKMesh-Principal", "X-Forwarded-User", "Authorization"):
            with self.subTest(header=header):
                self.assertEqual(
                    self.request("GET", "/api/v1/status", headers={header: "owner"}), base
                )
                status, _ = self.request("GET", "/api/v1/status", token=False, headers={header: "owner"})
                self.assertEqual(status, 403)

    def test_the_document_says_it_is_a_proposal_and_enforces_nothing(self):
        self.assertIn("**proposed**", self.text)
        flat = " ".join(self.text.split())
        self.assertIn("Nothing in this matrix may be read as already implemented", flat)


if __name__ == "__main__":
    unittest.main()
