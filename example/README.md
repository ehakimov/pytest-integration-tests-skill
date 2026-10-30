# Example project

A working integration test project built from the skills, and a demo stand it runs against without real services.

## Run

```bash
cd example
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium               # the browser is needed only for the UI test
cp .env.example .env

python demo_stand/server.py                         # in another terminal: http://127.0.0.1:8099
pytest -n 3 --alluredir allure-results --clean-alluredir
allure serve allure-results
```

Without a browser: `pytest -m "not ui" -n 3 --alluredir allure-results`. The Allure CLI is installed by the [guide](https://allurereport.org/docs/install/). The environment comes from `TEST_ENV=demo` in `.env` (or `--env=demo`). Stop the stand before running `tools/verify.py`: it starts its own.

## What comes from where

| Files | Source |
| --- | --- |
| `modules/{config,errors,http_client,auth,allure_helper,waiters,helper,kafka_client}.py`, `modules/web/fixtures.py`, `asserts/base_assert.py`, `conftest.py`, `requirements.txt`, `ruff.toml`, `CLAUDE.md`, `.gitignore` | `templates/` of the `pytest-integration-bootstrap` skill |
| `models/contracts/`, `modules/contracts/`, `asserts/contracts/`, `asserts/jsonschemas/`, `tests/contracts/conftest.py`, `tests/contracts/contract_create_test.py`, `modules/web/pages/login_page.py`, `modules/web/web_test_steps.py`, `asserts/web/web_asserts.py` | code blocks of the `pytest-integration-tests` skill (`SKILL.md`, `references/ui.md`) |
| `config.yml`, `.env.example`, `pytest.ini`, `demo_stand/`, the other tests, `demo_failures/` | written for the example |

Files from the first two rows are not edited by hand: change the skill and run `python tools/build_example.py` from the repository root. CI checks that the example is not behind the skills.

## Failures on purpose

`demo_failures/` shows how different causes of a failure look in the report. These tests are outside `testpaths` and are not part of the regular run:

```bash
pytest demo_failures -n 2 --alluredir allure-results   # without --clean-alluredir: added to the previous run
allure serve allure-results
```

| Test | Allure category | What to look at |
| --- | --- | --- |
| Product defect | Product defects | "expected 201, got 400" with the method, URL and response body |
| Timeout | Timed out waiting for a state | the "Waiting: ..." step: the polling history and the last response |
| No connection | Environment unavailable | `ConnectionError` after the retries, status broken |
| The gateway answers 503 | Environment unavailable | `EnvironmentUnavailable`, status broken, not a product defect |
| Broken test | Test defects | `KeyError` in the test data, status broken |
| UI | Product defects | a screenshot and `trace.zip` in Tear down (`playwright show-trace trace.zip`) |

## Your own environment

Add a block with the same keys to `config.yml`, put the secrets into `.env` and run `pytest --env=<environment>`. Kafka is not used in the example: the demo stand cannot provide it; the listener from `modules/kafka_client.py` is checked against a real broker by `tools/kafka_check.py` in CI.
