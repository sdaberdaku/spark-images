import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import render_readme  # noqa: E402

ROWS = [{"spark": "4.2.0", "scala": "2.13", "java": "21", "python": ["3.13.18", "3.14.10"]}]
README = "intro\n<!-- tags:start -->\nold\n<!-- tags:end -->\noutro\n"


class RenderTest(unittest.TestCase):
    def test_table_has_full_python_and_minor_tag(self):
        out = render_readme.render(README, ROWS)
        self.assertIn("| 4.2.0 | 2.13 | 21 | 3.13.18, 3.14.10 | `4.2.0-python3.13`, `4.2.0-python3.14` |", out)

    def test_outside_markers_untouched_and_idempotent(self):
        out = render_readme.render(README, ROWS)
        self.assertTrue(out.startswith("intro\n") and out.endswith("outro\n"))
        self.assertEqual(out, render_readme.render(out, ROWS))


if __name__ == "__main__":
    unittest.main()
