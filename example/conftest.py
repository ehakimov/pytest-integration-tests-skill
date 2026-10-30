"""Root: environment selection, cfg, test phase results for fixtures, Allure report enrichment."""
import json
import os
import platform
import subprocess
from pathlib import Path

import pytest

pytest.register_assert_rewrite("asserts")  # detailed pytest diffs for plain assert inside asserts/

from modules.config import ROOT_DIR, load_config  # noqa: E402

pytest_plugins = ["modules.web.fixtures", "modules.kafka_client"]  # only what the project has (UI, Kafka)

# Categories match exception class names, not message texts: messages can be in any language.
# Allure puts "<module>.<Class>: <message>" into the status message; the first matching category wins.
_ENVIRONMENT = (r"modules\.errors\.EnvironmentUnavailable|requests\.exceptions\."
                r"(ConnectionError|ConnectTimeout|ReadTimeout|Timeout|SSLError|ProxyError|ChunkedEncodingError)")
CATEGORIES = [
    {"name": "Environment unavailable", "matchedStatuses": ["broken", "failed"],
     "messageRegex": rf"({_ENVIRONMENT}):[\s\S]*"},
    {"name": "Timed out waiting for a state", "matchedStatuses": ["failed"],
     "messageRegex": r"modules\.errors\.WaitTimeout:[\s\S]*"},
    {"name": "Product defects", "matchedStatuses": ["failed"]},
    {"name": "Test defects", "matchedStatuses": ["broken"]},
]


def pytest_addoption(parser):
    parser.addoption("--env", default=os.getenv("TEST_ENV"), help="environment from config.yml (or TEST_ENV)")
    parser.addoption("--headed", action="store_true", help="UI tests with a visible browser")


@pytest.fixture(scope="session")
def cfg(pytestconfig) -> dict:
    """Settings of the selected environment (config.yml). Read-only."""
    env = pytestconfig.getoption("env")
    if not env:  # no default on purpose: neither a person nor an agent runs tests against a stand by accident
        pytest.exit("Pass --env=<environment from config.yml> or set TEST_ENV", returncode=4)
    return load_config(env)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """item.rep_setup / rep_call / rep_teardown: for fixtures that need to know whether the test failed."""
    report = yield
    setattr(item, f"rep_{report.when}", report)
    return report


def pytest_sessionfinish(session):
    """environment.properties and categories.json in the alluredir: once, on the xdist controller."""
    alluredir = session.config.getoption("allure_report_dir", default=None)
    env = session.config.getoption("env")
    if not alluredir or not env or hasattr(session.config, "workerinput"):
        return
    props = {"env": env, **{f"url.{k}": v for k, v in load_config(env).get("urls", {}).items()},
             "python": platform.python_version(), "tests.commit": _git_commit()}
    path = Path(alluredir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "environment.properties").write_text("\n".join(f"{k}={v}" for k, v in props.items()), encoding="utf-8")
    (path / "categories.json").write_text(json.dumps(CATEGORIES, ensure_ascii=False, indent=2), encoding="utf-8")


def _git_commit() -> str:
    """The commit of the test repository: from CI variables, otherwise from git."""
    for var in ("CI_COMMIT_SHORT_SHA", "GITHUB_SHA", "BUILD_VCS_NUMBER", "GIT_COMMIT"):
        if os.getenv(var):
            return os.environ[var][:8]
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5,
                             cwd=ROOT_DIR)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
