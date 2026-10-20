"""The «Обучение» page's live strip, version card and answers side by side: the video card's
numbers from nvidia-smi, where a version came from, and questions picked from the exam."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import blind
from backend import training_center as tc
from tests.test_learning_lab import LabBase

ROOT = Path(__file__).resolve().parents[1]


def smi(stdout, code=0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr="")


class GpuNowTests(unittest.TestCase):
    def setUp(self):
        tc._GPU_CACHE.update(t=0.0, value=None)

    def tearDown(self):
        tc._GPU_CACHE.update(t=0.0, value=None)

    def test_reads_temperature_load_and_memory(self):
        with mock.patch.object(tc.shutil, "which", lambda name: "nvidia-smi"), \
                mock.patch.object(tc.subprocess, "run", lambda *a, **kw: smi("78, 97, 2365, 4096, 61.40\n")):
            gpu = tc.gpu_now()
        self.assertEqual((gpu["temperature"], gpu["load"], gpu["power"]), (78.0, 97.0, 61.4))
        self.assertEqual((gpu["memory_used"], gpu["memory_total"]), (2365 * 1048576, 4096 * 1048576))
        self.assertFalse(gpu["hot"])

    def test_hot_card_hidden_values_and_no_driver(self):
        with mock.patch.object(tc.shutil, "which", lambda name: "nvidia-smi"), \
                mock.patch.object(tc.subprocess, "run", lambda *a, **kw: smi("88, 99, 3000, 4096, [N/A]\n")):
            gpu = tc.gpu_now()
        self.assertTrue(gpu["hot"])
        self.assertIsNone(gpu["power"])
        tc._GPU_CACHE.update(t=0.0)
        with mock.patch.object(tc.shutil, "which", lambda name: None):
            self.assertIsNone(tc.gpu_now())
        tc._GPU_CACHE.update(t=0.0)

        def broken(*a, **kw):
            raise subprocess.TimeoutExpired("nvidia-smi", 3)
        with mock.patch.object(tc.shutil, "which", lambda name: "nvidia-smi"), mock.patch.object(tc.subprocess, "run", broken):
            self.assertIsNone(tc.gpu_now())

    def test_cached_between_page_polls(self):
        calls = []

        def run(*a, **kw):
            calls.append(1)
            return smi("60, 50, 1000, 4096, 30\n")
        with mock.patch.object(tc.shutil, "which", lambda name: "nvidia-smi"), mock.patch.object(tc.subprocess, "run", run):
            tc.gpu_now()
            tc.gpu_now()
        self.assertEqual(len(calls), 1)


class OriginTests(LabBase):
    def make(self, run_id, config, **info):
        path = tc.folder() / "runs" / run_id
        path.mkdir(parents=True)
        tc._write(path / "run.json", dict({"id": run_id, "mode": "long", "config": config, "dataset": "d.json"}, **info))
        return tc._summary(path)

    def test_changes_in_words(self):
        parent = {"layers": 4, "width": 320, "arch": {"lab": True}}
        child = {"layers": 6, "width": 320, "arch": {"lab": True, "mixer": "hybrid", "fast": True, "loops": 1},
                 "rule": {"ff": True}}
        self.assertEqual(tc.changes(parent, child),
                         ["слоёв: 4 → 6", "слои: внимание → Mamba + внимание", "+ быстрые веса", "+ разгон Forward-Forward"])
        self.assertEqual(tc.changes(child, parent)[-2:], ["− быстрые веса", "− разгон Forward-Forward"])
        self.assertEqual(tc.changes(parent, dict(parent, seed=7, batch_size=8)), [])

    def test_origin_names_one_parent_and_what_changed(self):
        base = {"layers": 4, "width": 320, "arch": {"lab": True}}
        self.assertIsNone(self.make("20261019-010000-long", base)["origin"])
        grown = self.make("20261019-020000-long", dict(base, layers=6), grown_from="20261019-010000-long",
                          parent="20261019-010000-long", dataset="e.json")
        self.assertEqual(grown["origin"], {"how": "grown", "runs": ["20261019-010000-long"],
                                           "changes": ["слоёв: 4 → 6", "данные: e.json"]})
        self.assertEqual(grown["width"], 320)
        merged = self.make("20261019-030000-long", base, merged=["20261019-010000-long", "20261019-020000-long"])
        self.assertEqual(merged["origin"]["how"], "merged")
        orphan = self.make("20261019-040000-long", base, parent="20261001-010000-long")
        self.assertTrue(orphan["origin"]["missing"])

    def test_compare_without_questions_takes_them_from_the_exam(self):
        a = self.make("20261019-010000-long", {"layers": 4})
        (tc._run_dir(a["id"]) / "language-longrun.pt.best.pt").write_bytes(b"x")
        picked = []
        with mock.patch.object(blind, "_questions", lambda ids, count: picked.append(count) or ["Как дела?", "Что ты умеешь?"]), \
                mock.patch("backend.neural_language_benchmark.load_candidate", lambda path: (None, {"step": 5})), \
                mock.patch.object(tc, "_answer", lambda model, state, q, n: "ответ на " + q), \
                mock.patch.object(tc, "_with_tools", lambda text: text):
            r = tc.compare([a["id"]], [])
        self.assertEqual(picked, [3])
        self.assertTrue(r["picked"])
        self.assertEqual(r["versions"][0]["answers"], ["ответ на Как дела?", "ответ на Что ты умеешь?"])
        self.assertIn("из экзамена", r["note"])


class PageTests(unittest.TestCase):
    def test_live_strip_card_and_answers_are_on_the_page(self):
        html = (ROOT / "www" / "training.html").read_text(encoding="utf-8")
        js = (ROOT / "www" / "training.js").read_text(encoding="utf-8")
        dock = html[html.index('<div class="tabs-dock">'):html.index("<!-- ============ Обучение")]
        self.assertIn('role="tablist"', dock)
        self.assertIn('id="live-strip"', dock)
        for node in ("job-temp", "job-load", "job-vram", "job-hot", "prop-answers"):
            self.assertIn('id="%s"' % node, html)
        self.assertIn("function renderAnswers", js)
        self.assertIn("function versionCard", js)

    def test_three_tabs_with_sections_inside(self):
        import re
        html = (ROOT / "www" / "training.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'role="tab" id="tab-([a-z]+)"', html), ["today", "yorika", "settings"])
        for icon in ("today", "fox", "tune"):
            self.assertIn('data-icon="%s"' % icon, html)
        self.assertEqual(re.findall(r'data-sub="([a-z]+)"', html),
                         ["train", "brain", "evo", "exp", "night", "teacher", "data", "future"])
        for section in ("train", "brain", "evo", "exp", "night", "teacher", "data", "future"):
            self.assertEqual(html.count('id="pane-%s"' % section), 1)
        today = html[html.index('id="group-today"'):html.index('id="group-yorika"')]
        for part in ('id="wait-list"', 'id="proposal"', 'id="autopilot"', 'class="dawn"'):
            self.assertIn(part, today)

    def test_titles_carry_no_ordinal_numbers(self):
        for page in ("settings.html", "memory.html", "updates.html", "training.html"):
            self.assertNotIn("panel-index", (ROOT / "www" / page).read_text(encoding="utf-8"), page)
        self.assertNotIn("07–19", (ROOT / "www" / "training.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
