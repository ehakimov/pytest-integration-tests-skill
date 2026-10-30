"""
Packs every skill into a zip for uploading to the Claude app (Customize -> Skills -> + -> Create skill -> Upload a skill).

    python tools/package_skills.py   # dist/pytest-integration-tests.zip, dist/pytest-integration-bootstrap.zip

The archive holds the skill folder (SKILL.md, references/, templates/, scripts/); the folder name must equal
the name in SKILL.md. Hidden files and caches are left out.
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
KEEP_HIDDEN = {".env.example", ".gitignore", ".gitkeep"}  # template files that start with a dot


def included(path: Path, skill_dir: Path) -> bool:
    parts = path.relative_to(skill_dir).parts
    if "__pycache__" in parts or path.suffix == ".pyc":
        return False
    return all(not part.startswith(".") or part in KEEP_HIDDEN for part in parts)


def main() -> int:
    DIST.mkdir(exist_ok=True)
    for skill_dir in sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()):
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        name = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        if not name or name.group(1) != skill_dir.name:
            print(f"{skill_dir.name}: the name in SKILL.md differs from the folder name")
            return 1
        archive = DIST / f"{skill_dir.name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(skill_dir.rglob("*")):
                if file.is_file() and included(file, skill_dir):
                    zf.write(file, file.relative_to(skill_dir.parent))
        print(archive.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
