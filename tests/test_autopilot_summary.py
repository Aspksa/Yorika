"""The autopilot's one summary: what was tried, what helped, the growth curve, the brain map; and
the page folds manual activities away while the owner's own buttons stay."""
import re
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import archive
from backend import plans
from backend import summary
from backend import training_center as tc
from tests.test_learning_lab import LabBase

ROOT = Path(__file__).resolve().parents[1]


def iso(seconds_ago):
    return datetime.fromtimestamp(time.time() - seconds_ago, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SummaryTests(LabBase):
    def test_empty_folder_gives_an_empty_summary(self):
        built = summary.build()
        self.assertEqual(built["growth"], {"active": [], "record": []})
        self.assertEqual(built["tried"], [])
        self.assertIsNone(built["brain"])
        self.assertEqual(built["pareto"]["count"], 0)

    def test_tried_and_helped_by_activity_from_verdicts_and_the_archive(self):
        runs = [
            {"id": "r1", "mode": "long", "created": iso(3600), "kind": "sleep", "exam_per_char": 1.4, "verdict": {"result": "activated"}},
            {"id": "r2", "mode": "long", "created": iso(7200), "kind": "sleep", "exam_per_char": 1.5, "verdict": {"result": "rolled_back"}},
            {"id": "r3", "mode": "long", "created": iso(7200), "kind": "evolution", "exam_per_char": 1.3},
            {"id": "r4", "mode": "long", "created": iso(7200), "kind": "evolution", "exam_per_char": None},
            {"id": "r5", "mode": "long", "created": iso(3600), "kind": "branch", "exam_per_char": 1.4, "verdict": {"result": "waiting"}},
            {"id": "old", "mode": "long", "created": iso(30 * 24 * 3600), "kind": "sleep", "exam_per_char": 1.0},
        ]
        data = archive.load()
        data["log"].append({"run": "r3", "result": "вошла в архив"})
        archive._save(data)
        with mock.patch.object(tc, "runs", lambda: runs), \
                mock.patch.object(plans, "history", lambda: [{"kind": "dataevo", "runs": [{"id": "r5"}]}]):
            rows = {r["kind"]: r for r in summary.tried()}
        self.assertEqual((rows["sleep"]["tried"], rows["sleep"]["helped"]), (2, 1))
        self.assertEqual((rows["evolution"]["tried"], rows["evolution"]["helped"], rows["evolution"]["waiting"]), (1, 1, 1))
        self.assertEqual((rows["dataevo"]["title"], rows["dataevo"]["helped"]), ("Эволюция уроков", 1))

    def test_growth_follows_active_versions_and_the_record(self):
        runs = [{"id": "a", "created": "2026-10-01T00:00:00Z", "exam_per_char": 1.6},
                {"id": "b", "created": "2026-10-02T00:00:00Z", "exam_per_char": 1.7},
                {"id": "c", "created": "2026-10-03T00:00:00Z", "exam_per_char": 1.4}]
        tc._write(tc.folder() / "active-history.json", [{"meta": {"run": "a", "activated": "2026-10-01T01:00:00Z"}}])
        with mock.patch.object(tc, "runs", lambda: runs), \
                mock.patch.object(tc, "active", lambda: {"run": "c", "activated": "2026-10-03T01:00:00Z"}):
            g = summary.growth()
        self.assertEqual([p["run"] for p in g["active"]], ["a", "c"])
        self.assertEqual([p["exam"] for p in g["record"]], [1.6, 1.4])


class PageTests(unittest.TestCase):
    def test_manual_activities_fold_but_owner_buttons_never_do(self):
        html = (ROOT / "www" / "training.html").read_text(encoding="utf-8")
        css = (ROOT / "www" / "training.css").read_text(encoding="utf-8")
        self.assertIn(".auto-hide .manual,.auto-hide [data-evo-plan],.auto-hide [data-mind-go]{display:none!important}", css)
        for owner in ("stop-all", "ex-go"):
            tag = re.search(r"<[^>]*id=\"%s\"[^>]*>" % owner, html).group(0)
            self.assertNotIn("data-evo-plan", tag)
            self.assertNotIn("manual", tag)
        for chart in ("ch-growth", "ch-tried", "ch-pareto", "ch-brain"):
            self.assertIn('id="%s"' % chart, html)


if __name__ == "__main__":
    unittest.main()
