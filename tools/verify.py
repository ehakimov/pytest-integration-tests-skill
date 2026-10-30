"""
Full check of the repository: the example is built from the skills, the tests pass, the Allure report is as promised.

    python tools/verify.py            # everything, including UI (needs: python -m playwright install chromium)
    python tools/verify.py --skip-ui  # without a browser

What is checked:
1. example/ matches the skills (tools/build_example.py --check); ruff passes the layer rules.
2. The demo stand starts on a free port, the example tests pass in 3 workers (pytest-xdist).
3. allure-results has environment.properties and categories.json; parametrized titles are readable;
   at most one token per worker; no demo secret appears anywhere in allure-results.
4. HttpClient retries GET through two 503s and never repeats a POST.
5. The demo failures land in their report categories; a failed UI test attaches a screenshot and a trace.
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "example"
RESULTS = EXAMPLE / "allure-results"
PORT = 8099  # example/config.yml points here
STAND = f"http://127.0.0.1:{PORT}"
WORKERS = 3
SECRETS = ("autotest-pass", "demo-client-secret", "demo-token-")  # from .env.example and the demo stand

EXPECTED_CATEGORIES = {  # title of a demo failure -> report category
    "Product defect: the service rejects a request the test considers valid": "Product defects",
    "Timeout: the contract does not reach the status": "Timed out waiting for a state",
    "Environment unavailable: no connection": "Environment unavailable",
    "Environment unavailable: the gateway answers 503": "Environment unavailable",
    "Broken test: an error in the test data": "Test defects",
    "UI: waiting for the greeting after signing in with a wrong password": "Product defects",
}
EXPECTED_TITLES = ("Contract creation: no number -> 400", "Contract creation: planId is not a UUID -> 400")


def env_from_example() -> dict:
    env = dict(os.environ)
    for line in (EXAMPLE / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip())
    return env


def stand_get(path: str) -> dict:
    with urllib.request.urlopen(STAND + path, timeout=2) as response:
        return json.loads(response.read())


def start_stand(env: dict) -> subprocess.Popen:
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"Port {PORT} is busy: stop the demo stand started by hand (or whatever listens there)")
    stand = subprocess.Popen([sys.executable, "demo_stand/server.py"], cwd=EXAMPLE, env={**env, "STAND_PORT": str(PORT)})
    for _ in range(50):
        if stand.poll() is not None:
            raise SystemExit(f"The demo stand exited with code {stand.returncode}")
        try:
            stand_get("/debug/token_calls")
            return stand
        except OSError:
            time.sleep(0.2)
    stand.terminate()
    raise SystemExit(f"The demo stand did not start on {STAND}")


def pytest(args: list, env: dict, capture: bool = False) -> subprocess.CompletedProcess:
    if not capture:
        print("$ pytest " + " ".join(args), flush=True)
    return subprocess.run([sys.executable, "-m", "pytest", *args], cwd=EXAMPLE, env=env, text=True,
                          capture_output=capture, check=False)


def results() -> dict:
    """Test title -> result (the latest by time if a test ran several times)."""
    found = {}
    for file in RESULTS.glob("*-result.json"):
        data = json.loads(file.read_text(encoding="utf-8"))
        if data["name"] not in found or data.get("stop", 0) > found[data["name"]].get("stop", 0):
            found[data["name"]] = data
    return found


def category(result: dict, categories: list) -> str:
    """The same matching as Allure: the first category whose statuses and regex match."""
    message = (result.get("statusDetails") or {}).get("message", "")
    for cat in categories:
        regex = cat.get("messageRegex")
        if result["status"] in cat["matchedStatuses"] and (regex is None or re.fullmatch(regex, message)):
            return cat["name"]
    return "-"


def check_retries(env: dict) -> list:
    """GET survives two 503s; POST on 503 is sent exactly once."""
    os.environ.update({k: v for k, v in env.items() if k not in os.environ})
    sys.path.insert(0, str(EXAMPLE))  # the import below needs the example on sys.path
    from modules.http_client import HttpClient

    errors, client = [], HttpClient(STAND + "/api/v1", timeout=5)
    key = uuid.uuid4().hex
    response = client.get("flaky", params={"key": key}, attach=False)
    if response.status_code != 200 or stand_get(f"/debug/calls?key={key}")["calls"] != 3:
        errors.append(f"GET was not retried through two 503s: {response.status_code}")
    key = uuid.uuid4().hex
    client.post("flaky", params={"key": key}, attach=False)
    if (calls := stand_get(f"/debug/calls?key={key}")["calls"]) != 1:
        errors.append(f"POST on 503 was sent {calls} times: a business action would run twice")
    return errors


def collected(marker: list, env: dict) -> int:
    out = pytest(["--collect-only", "-q", *marker], env, capture=True).stdout
    return sum(1 for line in out.splitlines() if "::" in line)


def main() -> int:
    skip_ui = "--skip-ui" in sys.argv
    marker = ["-m", "not ui"] if skip_ui else []
    errors = []

    if subprocess.run([sys.executable, str(ROOT / "tools/build_example.py"), "--check"], check=False).returncode:
        return 1
    if subprocess.run([sys.executable, "-m", "ruff", "check", "."], cwd=EXAMPLE, check=False).returncode:
        errors.append("ruff found layer rule violations in example/")

    env = {**env_from_example(), "TEST_ENV": "demo"}
    stand = start_stand(env)
    try:
        tokens_before = stand_get("/debug/token_calls")["token_calls"]
        expected = collected(marker, env)
        if pytest(["-n", str(WORKERS), "--alluredir", str(RESULTS), "--clean-alluredir", *marker], env).returncode:
            errors.append("the example tests failed")
        main_results = results()
        passed = [name for name, r in main_results.items() if r["status"] == "passed"]
        if len(passed) != expected:
            errors.append(f"expected {expected} passed tests, got {len(passed)}")
        missing = [t for t in EXPECTED_TITLES if t not in main_results]
        if missing:
            errors.append(f"parametrized titles are not readable, missing: {missing}")
        for meta in ("environment.properties", "categories.json"):
            if not (RESULTS / meta).exists():
                errors.append(f"no {meta} in allure-results")
        tokens = stand_get("/debug/token_calls")["token_calls"] - tokens_before
        if tokens > WORKERS:
            errors.append(f"{tokens} tokens issued for {WORKERS} workers: the token cache does not work")

        errors += check_retries(env)

        print("\nFailures on purpose (the errors below are expected):", flush=True)
        pytest(["demo_failures", "-n", "2", "-q", "--tb=line", "--alluredir", str(RESULTS), *marker], env)
        categories = json.loads((RESULTS / "categories.json").read_text(encoding="utf-8"))
        all_results = results()
        for title, expected_category in EXPECTED_CATEGORIES.items():
            if skip_ui and title.startswith("UI:"):
                continue
            actual = category(all_results[title], categories) if title in all_results else "did not run"
            print(f"  {'OK ' if actual == expected_category else 'ERR'} {title} -> {actual}")
            if actual != expected_category:
                errors.append(f"\"{title}\": category {actual}, expected {expected_category}")
        if not skip_ui:
            names = {a["name"] for f in RESULTS.glob("*-container.json")
                     for part in ("befores", "afters") for fx in json.loads(f.read_text("utf-8")).get(part, [])
                     for a in fx.get("attachments", [])}
            for prefix in ("Screenshot on failure", "Playwright trace"):
                if not any(name.startswith(prefix) for name in names):
                    errors.append(f"the failed UI test did not attach \"{prefix}\"")
        for file in RESULTS.iterdir():
            if file.suffix in (".json", ".txt", ".properties") and any(s in file.read_text("utf-8", "replace")
                                                                     for s in SECRETS):
                errors.append(f"a demo secret leaked into allure-results/{file.name}")
    finally:
        stand.terminate()
        stand.wait(timeout=5)

    if errors:
        print("\nThe check failed:\n  - " + "\n  - ".join(errors))
        return 1
    print(f"\nAll good. Report: allure serve {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
