import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import render_readme  # noqa: E402

ROWS = [{"spark": "4.2.0", "scala": "2.13", "java": "21", "python": ["3.13.18", "3.14.10"]}]
README = "intro\n<!-- tags:start -->\nold\n<!-- tags:end -->\noutro\n"


class RenderTest(unittest.TestCase):
    def test_one_row_per_minor_tag_and_patch_bump_is_stable(self):
        out = render_readme.render(README, ROWS)
        self.assertIn("| `ghcr.io/sdaberdaku/spark:4.2-python3.14` | 2.13 | 21 |", out)
        bumped = [{**ROWS[0], "spark": "4.2.1", "python": ["3.13.19", "3.14.11"]}]
        self.assertEqual(out, render_readme.render(README, bumped))

    def test_renovate_python_regex_finds_every_python_version(self):
        root = Path(__file__).resolve().parent.parent
        pattern = json.loads((root / "renovate.json").read_text())["customManagers"][1]["matchStrings"][0]
        pattern = pattern.replace("(?<currentValue>", "(?P<currentValue>")
        text = (root / "images.json").read_text()
        expected = [v for r in json.loads(text) for v in r["python"]]
        self.assertEqual(re.findall(pattern, text), expected)

    def test_outside_markers_untouched_and_idempotent(self):
        out = render_readme.render(README, ROWS)
        self.assertTrue(out.startswith("intro\n") and out.endswith("outro\n"))
        self.assertEqual(out, render_readme.render(out, ROWS))


if __name__ == "__main__":
    unittest.main()
