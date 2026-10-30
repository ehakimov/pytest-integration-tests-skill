# Integration tests: rules for agents

Stack: pytest, requests, Allure, pytest-xdist (+ Playwright for UI, confluent-kafka for events).
Skills: pytest-integration-tests (writing tests), pytest-integration-bootstrap (the core).

## Commands
- `cp .env.example .env` and fill in the secrets
- `pytest --env=staging -m <marker> -n 4 --alluredir allure-results` then `allure serve allure-results`
- one test: `pytest --env=staging tests/<domain>/<file>_test.py::<test>`
- `pytest --collect-only -q` and `ruff check .` before handing over

## Layers
models/ -> modules/<domain>/*_client_v1.py -> modules/<domain>/*_test_steps.py -> tests/<domain>/*_test.py -> asserts/

## Rules
- A test calls only steps and `assert_*`: no `assert`, HTTP, `if`/`for`/`sleep`/`try`.
- All HTTP goes through `HttpClient`; authorization is a profile in `config.yml`.
- Attachments only through `modules/allure_helper.py`; waiting only through `wait_until`.
- Secrets only in `.env` and CI variables; a new variable goes to `.env.example`.
- A new marker goes to `pytest.ini`.
- Never invent `@allure.id`: it comes from an existing test case in Allure TestOps.
- Run only the new or changed tests against a shared environment, not the whole suite.
