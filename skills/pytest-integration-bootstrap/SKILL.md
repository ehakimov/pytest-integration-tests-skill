---
name: pytest-integration-bootstrap
description: Creates and repairs the core of a pytest integration test project from ready template files: HttpClient with timeouts, safe retries and masked Allure attachments, OAuth2 / Basic / API key profiles with a token cache, config.yml and .env, wait_until, Allure report categories, Playwright fixtures, a Kafka listener, ruff layer rules, GitLab or GitHub CI with optional Allure TestOps. Use it when starting a new test project, moving tests to a new job, or fixing timeouts, expiring tokens, attachments, parallel runs or CI of integration tests.
license: MIT
---

# The core of a pytest integration test project

The base the **pytest-integration-tests** skill stands on: that skill covers layers, tests, steps and assertions; this one covers the infrastructure. The core is not described here as code to retype: it is in real files in `templates/` next to this file, verified by running (pytest 8–9, allure-pytest 2.13, pytest-xdist 3.6, Playwright 1.6x).

## When and how

- **A new project.** First find out, if unknown: environments and URLs; authorization (OAuth2 password / client_credentials and the token URL, Basic, API key, none); whether UI and Kafka are needed; the CI (GitLab, GitHub, other) and whether there is Allure TestOps; the language of the report. Then:
  1. `python <this skill's directory>/scripts/scaffold.py --dest <project> [--without ui kafka] [--ci gitlab|github]`
  2. Fill in `config.yml` (environments, URLs, auth profiles) and `.env.example`; `cp .env.example .env`.
  3. `pip install -r requirements.txt` (+ `python -m playwright install chromium` for UI), `pytest --collect-only -q`, `ruff check .`.
  4. Write the first test with the pytest-integration-tests skill and go through "Checking the core" below.
- **An existing project.** Never rewrite the core as a whole and never overwrite files: the script skips existing ones. Find the symptom in "Common breakages", read the matching template (`templates/modules/auth.py` ...) and move the needed piece over, keeping the signatures the tests already call (an adapter or a gradual migration). One file into an empty spot: `scaffold.py --dest . --only modules/waiters.py`. A change of the core is a separate change with a run of the full suite.
- Take only what is needed: without UI there is no `modules/web/` and no Playwright, without Kafka no `modules/kafka_client.py` (`--without` drops the files, the requirements and the `pytest_plugins` entries).
- The messages in the templates are in English. If the project's reports are in another language, translate the step titles and messages; the report categories do not depend on the texts.

## What the script writes

```
<project>/
├── CLAUDE.md            rules for agents: commands, layers, conventions
├── config.yml           environments: URLs, auth profiles, reference ids, topics; no secrets
├── .env.example         names of secrets (.env is in .gitignore; in CI: CI/CD variables with the same names)
├── pytest.ini  conftest.py  requirements.txt (pinned)  ruff.toml  .gitignore
├── modules/             config, errors, http_client, auth, allure_helper, waiters, helper (+ web/, kafka_client.py)
├── models/  asserts/    base_assert.py, jsonschemas/
└── tests/               files/ ; <domain>/ appear with the first tests, __init__.py in every folder
```

The folder is `tests/`, not `test/`: `test` is a package of the Python standard library. `pytest-playwright` is not installed: its fixtures and options (`browser`, `page`, `--headed`) clash with the core's.

## Decisions in the core and why

| File | What it does | Why this way |
|---|---|---|
| `modules/http_client.py` | the only HTTP entry: timeout on every request, two Allure attachments per call, a masked log line | a session (connection pool) is shared per process; cookies are not kept, so they do not travel between tests |
| ″ `RETRY` | a failed connection is retried for any method; 502/503/504 only for GET/HEAD/OPTIONS; `Retry-After` is ignored | a repeated POST/PUT/DELETE may run a business action twice; a maintenance page with `Retry-After: 600` would hang each request for minutes. A truly idempotent PUT gets its own `Retry` in its client |
| `modules/auth.py` | profiles `type: oauth2` (default, password or client_credentials, `scope`/`audience`) / `basic` / `api_key`; `get_auth(cfg, None)` = no auth | the token is cached per process by the whole request form (another scope or user is another token) and refreshed before expiry; an unreachable token server raises `EnvironmentUnavailable`, rejected credentials `AuthError` |
| `modules/allure_helper.py` | attachments, masking | a key is secret if it contains `password`, `secret`, `token`, `apikey`, `authorization`, `cookie`... in any case and style (`accessToken`, `X-API-Key`); JSON, form bodies and query strings are masked, also in assertion messages; JSON over 50 000 characters is truncated; `X-Request-Id`-like headers go to the response attachment name |
| `modules/errors.py` | `EnvironmentUnavailable`, `AuthError`, `WaitTimeout` | the report categories match exception class names, so messages can be in any language |
| `modules/waiters.py` | `wait_until`: one step, the polling history and the last response, also when the wait breaks with an exception | an exception from probe stops the wait at once instead of polling a dead service until the timeout |
| `modules/helper.py` | `unique`, `iso_now` (milliseconds, `Z`), `as_instant` (timestamp normalizer), `to_dict`, `file_for_upload` (MIME by extension), `mutate` | Faker locale from `FAKER_LOCALE` |
| `asserts/base_assert.py` | `assert_status`, `json_body`, `field`, `assert_json_schema`, `assert_fields_match`, `assert_contains_item`, `assert_error` | any unexpected product answer (non-JSON body, missing field) is an AssertionError (failed), 502/503/504 are `EnvironmentUnavailable` (broken); schemas are checked with formats and validated themselves |
| `conftest.py` | `--env` (or `TEST_ENV`, no default on purpose), `cfg`, `item.rep_<phase>`, `environment.properties` and `categories.json` written once on the xdist controller | nobody runs tests against an environment by accident |
| `ruff.toml` | `assert` only in `asserts/`, no `requests`, `time.sleep`, `allure.attach`, `print` outside the core | the layer rules give feedback without a review |

Report categories, the first match wins: **Environment unavailable** (connection errors, timeouts, SSL/proxy errors, `EnvironmentUnavailable`) → **Timed out waiting for a state** (`WaitTimeout`) → **Product defects** (failed) → **Test defects** (broken).

## Configuration

`templates/config.yml` shows all keys: `verify_ssl`, `http_timeout`, `urls`, `auth.token_url` + `auth.profiles`, `ui_browser`, `ui_timeout_ms`, `ui_test_id_attribute`, `ui_users`, `kafka`. Secrets are never in it, only the names of environment variables (`*_env`). Shared values of several environments go to a YAML anchor. The values in `environment.properties` should stay ASCII: it is a Java properties file.

## UI (Playwright)

`modules/web/fixtures.py`: a browser per worker (`ui_browser`: chromium / firefox / webkit, `--headed` for a visible one), a clean context per test with the `ui_test_id_attribute`, on failure a screenshot and `trace.zip` in Tear down. The context is closed even if the screenshot fails. In CI use the image `mcr.microsoft.com/playwright/python:v<version from requirements>-noble` or `python -m playwright install --with-deps chromium`.

## Kafka

`modules/kafka_client.py`: `kafka_send` waits for the broker's acknowledgement and fails on a rejected message (`flush()` alone only counts unsent ones). `KafkaListener` starts at the current end of every partition without a consumer group or commits; a missing topic or an unreachable broker fails at once; a message it cannot decode is kept as bytes and never stops the listener; listener errors are attached on a timeout. Avro or Protobuf: pass `value_deserializer=`.

## CI

- `--ci gitlab` writes `.gitlab-ci.yml`, `--ci github` writes `.github/workflows/autotests.yml`; another CI repeats the same steps: install, `pytest -m "$TEST_MARK" --env="$TEST_ENV" -n N --alluredir=allure-results --junitxml=report.xml`, keep `allure-results` and `report.xml` as artifacts.
- Marker sets are defined once (YAML anchors in GitLab, workflow inputs in GitHub). A scheduled run fails the pipeline when tests fail; a manual run is `allow_failure`.
- Allure TestOps (optional): `ALLURE_ENDPOINT`, `ALLURE_TOKEN`, `ALLURE_PROJECT_ID` in CI variables, `ALLURE_RESULTS: allure-results`, and `./allurectl watch -- pytest ...`: it creates the launch itself and uploads results during the run (the `.testops` job in the GitLab template; combine with `extends: [.autotests, .testops]`). Do not split it into `launch create` in `script` and `launch close` in `after_script`: `after_script` runs in a separate shell and does not see variables set in `script`.
- Without TestOps: `allure generate allure-results -o allure-report` and publish it (Pages or an artifact). For trends copy `history/` of the previous report into `allure-results/history` before generating.
- A chat notification (`after_script`): totals from `report.xml`, the environment, the job, links to the pipeline and the report; the bot token is a CI variable.
- Secrets are masked CI variables with the same names as in `.env.example`: the core reads them from the environment.

## Checking the core

1. `pytest --collect-only -q` and `ruff check .`: imports, markers and layers are fine.
2. A smoke run: `pytest --env=<env> -m smoke -n 2 --alluredir allure-results`. `allure-results` has `environment.properties` and `categories.json`; HTTP steps have two attachments each; no secret is visible in the attachments, the `log` attachment or the messages.
3. Break an expected status in an assertion for a moment: the message has "expected / got / response", the category is "Product defects". Point a URL to a closed port: "Environment unavailable". Revert.
4. UI: a failed test attaches a screenshot and `trace.zip` (`playwright show-trace trace.zip`).

## Common breakages: what to take from the core

| Symptom | Cause | Fix |
|---|---|---|
| A CI job hangs until its timeout | requests without `timeout`; `Retry-After` respected | `HttpClient` (timeout from config, `respect_retry_after_header=False`) |
| 401 in the middle of a long run | a token fetched once in the client's `__init__` | `TokenAuth`: cache and refresh before expiry |
| A test with another scope gets 403 | the token cache key ignores scope or user | `TokenAuth` keys the cache by the whole form |
| Failures on 502/503 while the environment is deployed | no retries | `RETRY` for safe methods |
| Duplicated entities, "already submitted" after a 504 | POST/PUT/DELETE are retried on 5xx | `allowed_methods` = GET/HEAD/OPTIONS |
| The report has no service response when it is not JSON | the attachment is only `response.json()` + `except: pass` | `attach_http` |
| Tokens or passwords in the report | masking by exact snake_case keys only, raw bodies in messages | `allure_helper.is_secret`, `body_preview` |
| A product bug shows up as a "broken test" | `r.json()["id"]` in steps or assertions | `json_body`, `field`, defensive reading in steps |
| A stand outage shows up as a product defect | 503 raised as AssertionError | `assert_status` raises `EnvironmentUnavailable` |
| Waiting differs in every file, a step per attempt | own loops | `wait_until` |
| Can't tell an environment outage from a bug | no categories | `CATEGORIES` + `pytest_sessionfinish` |
| A Playwright trace sits in a folder and is not in the report | saved to a file, not attached | the `page` fixture |
| `--headless=False` runs headless | a string option: "False" is truthy | the `--headed` flag (`store_true`) |
| Hosts and passwords in code, a password in a run script | no config and secrets | `config.yml` + `.env` + CI variables |
| A Kafka test catches foreign messages or misses its own | a shared `group.id`, subscribing after the action | `KafkaListener` before the action |
| A Kafka test silently times out | an undecodable message killed the listener thread, or the topic does not exist | `KafkaListener` |
| A session fixture is created on every worker | no grouping | `xdist_group` + `--dist loadgroup` |
| A date in a model is "yesterday" after midnight | a value computed at import | `default_factory` |
| Non-ASCII parameter ids are shown as escape codes in the console and report.xml | pytest escapes ids | allure-pytest decodes `{param_id}` in titles itself; for the console add `disable_test_id_escaping_and_forfeit_all_rights_to_community_support = true` to `pytest.ini`, knowing that pytest maintainers do not support it |
