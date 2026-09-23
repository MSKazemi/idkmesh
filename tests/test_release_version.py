"""Release publication must bind one tag to one package version identity."""

from __future__ import annotations

import unittest

from tools import check_release_version as release_version


class ReleaseVersionTests(unittest.TestCase):
    def test_committed_version_sources_agree(self) -> None:
        self.assertEqual(
            release_version.pyproject_version(),
            release_version.package_version(),
        )

    def test_current_version_accepts_plain_v_and_refs_tags_forms(self) -> None:
        version = release_version.pyproject_version()
        for tag in (version, f"v{version}", f"refs/tags/v{version}"):
            with self.subTest(tag=tag):
                self.assertEqual(version, release_version.verify(tag))

    def test_mismatched_tag_is_rejected(self) -> None:
        with self.assertRaises(release_version.ReleaseVersionError):
            release_version.verify("v999.999.999")

    def test_whitespace_inside_tag_is_rejected(self) -> None:
        with self.assertRaises(release_version.ReleaseVersionError):
            release_version.version_from_tag("v0.1.0 bad")

    def test_empty_tag_is_rejected(self) -> None:
        with self.assertRaises(release_version.ReleaseVersionError):
            release_version.version_from_tag("  ")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
