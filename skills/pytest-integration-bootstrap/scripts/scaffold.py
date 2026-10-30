"""Copies the framework core from templates/ into a project.

    python scaffold.py --dest path/to/tests                 # core + UI + Kafka
    python scaffold.py --dest . --without ui kafka --ci gitlab
    python scaffold.py --dest . --only modules/auth.py      # one file, e.g. to fix an existing project
    python scaffold.py --dest . --dry-run                   # show what would be written

Existing files are never overwritten unless --force: in an existing project the agent compares and merges by hand.
Only the Python standard library is used.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
FEATURES = {  # feature -> files that belong only to it
    "ui": ["modules/web/__init__.py", "modules/web/fixtures.py"],
    "kafka": ["modules/kafka_client.py"],
}
PLUGINS = {"ui": "modules.web.fixtures", "kafka": "modules.kafka_client"}
CI = {"gitlab": ("ci/gitlab-ci.yml", ".gitlab-ci.yml"), "github": ("ci/github-actions.yml", ".github/workflows/autotests.yml")}


def render(rel: str, text: str, features: set[str]) -> str:
    """Drops what belongs to features that are not selected."""
    if rel == "conftest.py":
        plugins = ", ".join(f'"{PLUGINS[f]}"' for f in PLUGINS if f in features)
        text = re.sub(r"^pytest_plugins = \[.*?\]", f"pytest_plugins = [{plugins}]", text, count=1, flags=re.M)
    if rel == "requirements.txt":
        lines = []
        for line in text.splitlines():
            m = re.search(r"\s+# feature: (\w+)$", line)
            if m and m.group(1) not in features:
                continue
            lines.append(line[:m.start()] if m else line)
        text = "\n".join(lines) + "\n"
    return text


def plan(features: set[str], ci: str | None, only: list[str] | None) -> list[tuple[str, str]]:
    """[(template path, destination path)]."""
    excluded = {f for feature, files in FEATURES.items() if feature not in features for f in files}
    files = sorted(p.relative_to(TEMPLATES).as_posix() for p in TEMPLATES.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts)
    pairs = [(f, f) for f in files if not f.startswith("ci/") and f not in excluded]
    if ci:
        pairs.append(CI[ci])
    if only:
        unknown = set(only) - {src for src, _ in pairs}
        if unknown:
            sys.exit(f"No such template: {', '.join(sorted(unknown))}")
        pairs = [(src, dst) for src, dst in pairs if src in only]
    return pairs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--without", nargs="*", default=[], choices=sorted(FEATURES))
    parser.add_argument("--ci", choices=sorted(CI))
    parser.add_argument("--only", nargs="*", help="template paths to copy, e.g. modules/auth.py")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    features = set(FEATURES) - set(args.without)
    written, skipped = [], []
    for src, dst in plan(features, args.ci, args.only):
        target = args.dest / dst
        if target.exists() and not args.force:
            skipped.append(dst)
            continue
        written.append(dst)
        if args.dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = (TEMPLATES / src).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copyfile(TEMPLATES / src, target)
        else:
            target.write_text(render(src, text, features), encoding="utf-8")
    verb = "Would write" if args.dry_run else "Written"
    print(f"{verb} {len(written)}: " + (", ".join(written) or "-"))
    if skipped:
        print(f"Skipped {len(skipped)} existing (compare and merge by hand, or --force): " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
