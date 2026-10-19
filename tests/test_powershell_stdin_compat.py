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
        self.assertEqual(source.count("Write-ChildUtf8 $proc"), 3)
        # The background chat worker cannot see script functions and writes UTF-8 bytes itself.
        self.assertIn("$proc.StandardInput.BaseStream.Write($payload,0,$payload.Length)", source)

    def test_cloud_processes_use_the_compatibility_path(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "yorika-tray.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("cloud-ru-settings.py", source)
        self.assertIn("cloud-ru-stream.py", source)
        self.assertIn("cloud-ru-model.py", source)
        # memory-set/delete/edit read their JSON from stdin too; without it Settings memory controls fail.
        self.assertIn("if($action -in @('save','persona-config','persona-delete','memory-set','memory-delete','memory-edit')){Write-ChildUtf8 $proc $body}", source)

    def test_python_is_probed_not_just_found(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "yorika-tray.ps1").read_text(encoding="utf-8-sig")
        # The Microsoft Store python.exe stub must not be mistaken for a real interpreter.
        self.assertNotIn("Get-Command python.exe -ErrorAction SilentlyContinue", source)
        self.assertEqual(source.count("$python=Get-YorikaPython"), 5)
        self.assertEqual(source.count("$psi.Arguments=($python.Prefix+"), 5)
        self.assertIn("$version -match '^Python 3\\.'", source)

    def test_python_choice_is_pinned_and_store_key_is_synced(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "yorika-tray.ps1").read_text(encoding="utf-8-sig")
        # Store Python has a private %LOCALAPPDATA%; changing interpreters hid the saved key.
        self.assertIn("'Yorika\\python-interpreter.txt'", source)
        self.assertIn("LocalCache\\Local\\Yorika\\secrets\\cloud-ru.dpapi", source)
        self.assertLess(source.index("if(-not $mutex.WaitOne(0))"), source.index("\nSync-StorePythonSecrets\n"))


if __name__ == "__main__":
    unittest.main()
