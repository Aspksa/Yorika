"""Regression: Windows PowerShell 5.1 lacks ProcessStartInfo.StandardInputEncoding."""
import re
import unittest
from pathlib import Path


class PowerShellStdinCompatibility(unittest.TestCase):
    def test_child_process_stdin_is_explicit_utf8(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "yorika-tray.ps1").read_text(encoding="utf-8-sig")
        self.assertNotRegex(source, r"(?m)^\s*\$psi\.StandardInputEncoding\s*=")
        self.assertNotIn("$proc.StandardInput.Write(", source)
        self.assertIn("[Text.Encoding]::UTF8.GetBytes($value)", source)
        self.assertIn("$process.StandardInput.BaseStream.Write($data,0,$data.Length)", source)
        self.assertEqual(source.count("Write-ChildUtf8 $proc"), 5)

    def test_cloud_processes_use_the_compatibility_path(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "yorika-tray.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("cloud-ru-settings.py", source)
        self.assertIn("cloud-ru-stream.py", source)
        self.assertIn("cloud-ru-model.py", source)
        self.assertIn("if($action -in @('save','persona-config','persona-delete')){Write-ChildUtf8 $proc $body}", source)


if __name__ == "__main__":
    unittest.main()
