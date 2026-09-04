#!/usr/bin/env python3
"""Assert no NEW broken Markdown link exists outside the seeded test fixtures.

This logic previously lived only as an inline heredoc inside
`.github/workflows/pr-gate.yml`, which meant it could not be run locally and
could silently drift from whatever a developer checked by hand. It is a script
so that CI and `scripts/testkit.py integration` execute the same bytes.

Negative fixtures under `tests/fixtures/` contain deliberately broken links and
are excluded; everything else must resolve.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tools" / "idkgraph_link_check.py"


def main() -> int:
    if not CHECKER.exists():
        print(f"link checker not found: {CHECKER}", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode

    findings = [
        f
        for f in json.loads(proc.stdout)["findings"]
        if "tests/fixtures/" not in f["source_path"]
    ]
    for f in findings:
        print(f"{f['severity']}: {f['source_path']}:{f['line']} {f['message']}")
    print(f"non-fixture link findings: {len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
