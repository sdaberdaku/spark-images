import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import discover  # noqa: E402

PY = ["3.13.18", "3.14.10"]
ROWS = [
    {"spark": "3.5.9", "scala": "2.12", "java": "17", "python": ["3.11.18"]},
    {"spark": "4.2.0", "scala": "2.13", "java": "21", "python": PY},
]


def spark_tags(*versions):
    return [f"{v}-scala{s}-java{j}-ubuntu" for v in versions for s in ("2.12", "2.13") for j in ("17", "21", "25")]


class SparkTest(unittest.TestCase):
    def test_new_minor_gets_highest_patch_java21_and_newest_python_list(self):
        rows, added = discover.add_spark(ROWS, spark_tags("4.2.1", "4.3.0", "4.3.1"))
        self.assertEqual(added, ["spark 4.3"])
        self.assertEqual(rows[-1], {"spark": "4.3.1", "scala": "2.13", "java": "21", "python": PY})

    def test_new_major_and_minor_appended_in_version_order(self):
        rows, added = discover.add_spark(ROWS, spark_tags("5.0.0", "4.3.0"))
        self.assertEqual(added, ["spark 4.3", "spark 5.0"])
        self.assertEqual([r["spark"] for r in rows], ["3.5.9", "4.2.0", "4.3.0", "5.0.0"])

    def test_existing_line_patch_and_old_lines_ignored(self):
        rows, added = discover.add_spark(ROWS, spark_tags("4.2.1", "3.4.4", "3.5.10"))
        self.assertEqual((rows, added), (ROWS, []))

    def test_falls_back_when_scala_213_or_java_21_missing(self):
        rows, _ = discover.add_spark(ROWS, ["4.3.0-scala2.12-java17-ubuntu", "4.3.0-scala2.12-java25-ubuntu"])
        self.assertEqual((rows[-1]["scala"], rows[-1]["java"]), ("2.12", "25"))

    def test_input_rows_not_mutated(self):
        discover.add_spark(ROWS, spark_tags("4.3.0"))
        self.assertEqual(len(ROWS), 2)


class PythonTest(unittest.TestCase):
    def test_new_line_added_to_highest_spark_major_rows_only(self):
        rows, added = discover.add_python(ROWS, ["3.14.11-slim", "3.15.0-slim", "3.15.1-slim"])
        self.assertEqual(added, ["python 3.15"])
        self.assertEqual(rows[0]["python"], ["3.11.18"])
        self.assertEqual(rows[1]["python"], ["3.13.18", "3.14.10", "3.15.1"])

    def test_old_line_patch_and_prereleases_ignored(self):
        rows, added = discover.add_python(ROWS, ["3.14.11-slim", "3.15.0rc1-slim", "3.12.2-slim", "3.15.0-slim-bookworm"])
        self.assertEqual((rows, added), (ROWS, []))


class BothTest(unittest.TestCase):
    def test_new_spark_row_also_gets_new_python(self):
        rows, added = discover.discover(ROWS, spark_tags("4.3.0"), ["3.15.0-slim"])
        self.assertEqual(added, ["spark 4.3", "python 3.15"])
        self.assertEqual(rows[-1]["python"], ["3.13.18", "3.14.10", "3.15.0"])
        self.assertEqual(rows[1]["python"], ["3.13.18", "3.14.10", "3.15.0"])

    def test_nothing_new(self):
        self.assertEqual(discover.discover(ROWS, spark_tags("4.2.1"), ["3.14.11-slim"]), (ROWS, []))


class SerializeTest(unittest.TestCase):
    def test_layout_round_trips_and_renovate_regex_finds_every_python(self):
        rows, _ = discover.discover(ROWS, spark_tags("4.3.0"), ["3.15.0-slim"])
        text = discover.serialize(rows)
        self.assertEqual(json.loads(text), rows)
        self.assertTrue(text.startswith("[\n  {") and text.endswith("}\n]\n"))
        self.assertEqual(len(text.splitlines()), len(rows) + 2)
        root = Path(__file__).resolve().parent.parent
        pattern = json.loads((root / "renovate.json").read_text())["customManagers"][1]["matchStrings"][0]
        pattern = pattern.replace("(?<currentValue>", "(?P<currentValue>")
        self.assertEqual(re.findall(pattern, text), [v for r in rows for v in r["python"]])

    def test_current_images_json_is_already_in_canonical_layout(self):
        text = (Path(__file__).resolve().parent.parent / "images.json").read_text()
        self.assertEqual(discover.serialize(json.loads(text)), text)


if __name__ == "__main__":
    unittest.main()
