"""Regression tests for source archive filtering."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/ci-release-check.py"
spec = importlib.util.spec_from_file_location("ci_release_check", path)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseFilterTests(unittest.TestCase):
    def test_secret_extensions_are_excluded(self):
        for name in ("private.pem", "identity.key", "signing.p12", "cloud.dpapi",
                     "cert.pfx", ".env", ".env.production", ".netrc", "id_ed25519"):
            with self.subTest(name=name):
                self.assertFalse(release.eligible(Path(name)))

    def test_portable_runtime_is_excluded(self):
        self.assertFalse(release.eligible(Path("ЦЕНТР_YORIKA/python312-runtime/python.exe")))
        self.assertFalse(release.eligible(Path("ЦЕНТР_YORIKA/python-3.12.10-embed-amd64.zip")))

    def test_expected_source_is_included(self):
        self.assertTrue(release.eligible(Path("scripts/run-acceptance.py")))


if __name__ == "__main__":
    unittest.main()
