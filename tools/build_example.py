"""
Builds example/ from the skills: the skills are the source of truth, the generated files are never edited by hand.

- The core comes from skills/pytest-integration-bootstrap/templates/ (the same render as scripts/scaffold.py).
- Domain files come from code blocks of skills/pytest-integration-tests (SKILL.md and references/*.md) whose
  first line is a comment with the file path ("# modules/contracts/contract_client_v1.py").
Everything else in example/ (config.yml, .env.example, pytest.ini, the demo stand, the other tests, demo_failures)
is written for the example and left alone.

    python tools/build_example.py           # write the files into example/
    python tools/build_example.py --check   # only compare; exit code 1 if example/ is behind the skills
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "example"
BOOTSTRAP = ROOT / "skills" / "pytest-integration-bootstrap"
TESTS_SKILL = ROOT / "skills" / "pytest-integration-tests"
OWN_FILES = {"config.yml", ".env.example", "pytest.ini"}  # the example has its own: the demo environment
BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
PATH = re.compile(r"#\s+([\w./-]+\.py)\s*$")


def _scaffold():
    spec = importlib.util.spec_from_file_location("scaffold", BOOTSTRAP / "scripts" / "scaffold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generated() -> dict[str, bytes]:
    """Path in example/ -> content."""
    scaffold = _scaffold()
    features = set(scaffold.FEATURES)
    files: dict[str, bytes] = {}
    for src, dst in scaffold.plan(features, None, None):
        if dst in OWN_FILES:
            continue
        raw = (scaffold.TEMPLATES / src).read_bytes()
        try:
            files[dst] = scaffold.render(src, raw.decode("utf-8"), features).encode("utf-8")
        except UnicodeDecodeError:
            files[dst] = raw
    for doc in [TESTS_SKILL / "SKILL.md", *sorted((TESTS_SKILL / "references").glob("*.md"))]:
        for code in BLOCK.findall(doc.read_text(encoding="utf-8")):
            match = PATH.match(code.splitlines()[0])
            if not match:
                continue
            path = match.group(1)
            if path in files and files[path] != code.encode():
                sys.exit(f"Two different versions of {path} in the skills: keep one")
            files[path] = code.encode("utf-8")
    return files


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for rel, content in sorted(generated().items()):
        target = EXAMPLE / rel
        if target.exists() and target.read_bytes() == content:
            continue
        stale.append(rel)
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    if check:
        if stale:
            print("example/ is behind the skills, run python tools/build_example.py:\n  " + "\n  ".join(stale))
            return 1
        print("example/ matches the skills")
        return 0
    print(f"Files updated: {len(stale)}" + ("".join(f"\n  {s}" for s in stale)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
