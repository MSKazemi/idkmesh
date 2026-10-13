"""Executable consistency checks for the API metrics interval guide."""
from __future__ import annotations

import contextlib
import inspect
import io
from pathlib import Path
import re
import unittest

from idkmesh.otel_metrics import evaluate_api_metrics_interval

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "reference" / "API_METRICS_INTERVAL_GUIDE.md"


class ApiMetricsIntervalDocumentationTests(unittest.TestCase):
    def test_example_runs(self):
        text = GUIDE.read_text(encoding="utf-8")
        snippets = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
        self.assertEqual(len(snippets), 1)
        namespace = {"__name__": "interval_guide"}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            exec(compile(snippets[0], "<api-metrics-interval-guide>", "exec"), namespace)
        report = namespace["result"]
        self.assertEqual(report["status"], "measured")
        self.assertEqual(report["requests"], 3)
        self.assertEqual(report["within_1000ms"], 2)
        self.assertIn("'authority': 'none'", output.getvalue())

    def test_all_unknown_reasons_documented(self):
        source = inspect.getsource(evaluate_api_metrics_interval)
        reasons = set(re.findall(r'unknown\("([a-z_]+)"\)', source))
        self.assertGreaterEqual(len(reasons), 8)
        guide = GUIDE.read_text(encoding="utf-8")
        for reason in sorted(reasons):
            with self.subTest(reason=reason):
                self.assertIn(f"`{reason}`", guide)


if __name__ == "__main__":
    unittest.main()
