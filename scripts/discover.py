"""Add new Spark and Python lines found on Docker Hub to images.json.

Prints one addition per line ("spark 4.3", "python 3.15"); prints nothing when
there is nothing new. Always exits 0. Use --dry-run to print without writing.

Test hook: DISCOVER_FAKE_SPARK_TAGS (comma-separated Docker Hub tags, for
example "4.3.0-scala2.13-java21-ubuntu") is added to the Spark tag list.
"""
import json
import os
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HUB = "https://hub.docker.com/v2/repositories/library/{}/tags?page_size=100&name={}"
SPARK_TAG = re.compile(r"^(\d+)\.(\d+)\.(\d+)-scala(\d+\.\d+)-java(\d+)-ubuntu$")
PYTHON_TAG = re.compile(r"^(\d+)\.(\d+)\.(\d+)-slim$")
MIN_SPARK = (3, 5)


def vtuple(version):
    return tuple(int(p) for p in version.split("."))


def add_spark(rows, tags):
    """Append a row for every Spark major.minor line not in rows (3.5 and up)."""
    rows = [dict(r) for r in rows]
    known = {vtuple(r["spark"])[:2] for r in rows}
    template = max(rows, key=lambda r: vtuple(r["spark"]))["python"]
    lines = {}
    for tag in tags:
        m = SPARK_TAG.match(tag)
        if not m:
            continue
        major, minor, patch, scala, java = int(m[1]), int(m[2]), int(m[3]), m[4], int(m[5])
        if (major, minor) >= MIN_SPARK and (major, minor) not in known:
            lines.setdefault((major, minor), []).append((patch, scala, java))
    added = []
    for line in sorted(lines):
        found = lines[line]
        patch = max(p for p, _, _ in found)
        scalas = {s for p, s, _ in found if p == patch}
        javas = {j for p, _, j in found if p == patch}
        scala = "2.13" if "2.13" in scalas else max(scalas, key=vtuple)
        java = 21 if 21 in javas else max(javas)
        rows.append({"spark": f"{line[0]}.{line[1]}.{patch}", "scala": scala, "java": str(java), "python": list(template)})
        added.append(f"spark {line[0]}.{line[1]}")
    return rows, added


def add_python(rows, tags):
    """Add the highest patch of every Python line newer than any in rows to the rows of the highest Spark major."""
    rows = [dict(r) for r in rows]
    newest = max(vtuple(p)[:2] for r in rows for p in r["python"])
    lines = {}
    for tag in tags:
        m = PYTHON_TAG.match(tag)
        if m:
            version = tuple(int(g) for g in m.groups())
            if version[:2] > newest:
                lines[version[:2]] = max(lines.get(version[:2], version), version)
    top = max(vtuple(r["spark"])[0] for r in rows)
    added = []
    for line in sorted(lines):
        full = ".".join(map(str, lines[line]))
        for r in rows:
            if vtuple(r["spark"])[0] == top:
                r["python"] = sorted(r["python"] + [full], key=vtuple)
        added.append(f"python {line[0]}.{line[1]}")
    return rows, added


def discover(rows, spark_tags, python_tags):
    rows, spark = add_spark(rows, spark_tags)
    rows, python = add_python(rows, python_tags)
    return rows, spark + python


def serialize(rows):
    """One row per line with inline arrays; Renovate's regex needs this layout."""
    return "[\n" + ",\n".join("  " + json.dumps(r) for r in rows) + "\n]\n"


def fetch_tags(repo, name):
    url, tags = HUB.format(repo, name), []
    while url:
        with urllib.request.urlopen(url, timeout=30) as resp:
            page = json.load(resp)
        tags += [t["name"] for t in page["results"]]
        url = page.get("next")
    return tags


def main(argv):
    path = ROOT / "images.json"
    rows = json.loads(path.read_text())
    spark_tags = fetch_tags("spark", "-ubuntu") + [t for t in os.environ.get("DISCOVER_FAKE_SPARK_TAGS", "").split(",") if t]
    new_rows, added = discover(rows, spark_tags, fetch_tags("python", "-slim"))
    if added and "--dry-run" not in argv:
        path.write_text(serialize(new_rows))
    if added:
        print("\n".join(added))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
