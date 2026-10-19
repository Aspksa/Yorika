"""Regression: public updater works without a GitHub token; Python child output is UTF-8."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PublicUpdaterCompatibility(unittest.TestCase):
    def test_public_request_no_longer_requires_token(self):
        ps = (ROOT / "scripts/update-engine.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("if(-not $t){throw 'Токен отсутствует", ps)
        self.assertIn("if($StrictCandidate){$CandidateToken}else{''}", ps)
        self.assertIn("if($t){$headers.Authorization", ps)
        self.assertIn("https://api.github.com/repos/Aspksa/Yorika/commits/main", ps)

    def test_all_python_children_emit_utf8(self):
        ps = (ROOT / "scripts/yorika-tray.ps1").read_text(encoding="utf-8-sig")
        self.assertEqual(ps.count("$psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'"), 6)
        self.assertIn("$psi.StandardOutputEncoding=[Text.Encoding]::UTF8", ps)

    def test_public_ui_is_clear(self):
        html = (ROOT / "www/updates.html").read_text(encoding="utf-8")
        self.assertIn("токен не нужен", html)

if __name__ == "__main__":
    unittest.main()
