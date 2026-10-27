"""Render the tag table of README.md from images.json. Use --check to fail when stale."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
START, END = "<!-- tags:start -->", "<!-- tags:end -->"


def minor(version):
    return ".".join(version.split(".")[:2])


def table(rows):
    lines = [
        "| Tag | Scala | Java |",
        "| --- | ----- | ---- |",
    ]
    for r in rows:
        for p in r["python"]:
            tag = f"ghcr.io/sdaberdaku/spark:{minor(r['spark'])}-python{minor(p)}"
            lines.append(f"| `{tag}` | {r['scala']} | {r['java']} |")
    return "\n".join(lines)


def render(readme, rows):
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{table(rows)}\n{END}{tail}"


def main(argv):
    readme_path = ROOT / "README.md"
    old = readme_path.read_text()
    new = render(old, json.loads((ROOT / "images.json").read_text()))
    if "--check" in argv:
        if old != new:
            print("README.md tag table is stale; run scripts/render_readme.py", file=sys.stderr)
            return 1
        return 0
    readme_path.write_text(new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
