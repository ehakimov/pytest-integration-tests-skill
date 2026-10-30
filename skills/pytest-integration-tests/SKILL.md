---
name: pytest-integration-tests
description: Writes, extends and reviews Python integration tests against deployed services (pytest with requests, Playwright or Kafka) in layers models → client → steps → test → asserts, with readable Allure reports and safe pytest-xdist runs. Use it to cover an endpoint, a service or a task with tests, to add a client, steps, assertions or fixtures, to investigate a failed or flaky integration test, or when an OpenAPI/Swagger spec is shared with a request like "write an autotest" or "напиши автотест". Not for unit tests with mocks or in-process test clients.
license: MIT
---

# Integration tests with pytest: layers, Allure, xdist

Integration tests run against deployed services on test environments: API, UI and asynchronous events.

The goal: a test reads like a business scenario, the Allure report explains a failure without reading code, and tests run safely in parallel on any environment.

The infrastructure (HttpClient, authorization, attachments, `wait_until`, report hooks, UI fixtures, Kafka, CI) lives in the **pytest-integration-bootstrap** skill. Load it when the project has no core yet, the project is new, or something in the core needs fixing.

## Workflow

1. **Existing project first.** Read CLAUDE.md / README / agent rules (`.cursor/rules` and similar), `pytest.ini`, the root `conftest.py`, the config and one or two tests of a neighbouring domain. The project's conventions win over this skill: folder and class names, suffixes, language, the fixture and helper format. Take from the skill what the project lacks, plus the quality rules. Do not rewrite the core unasked: if you see a problem, say so.
2. **Source of truth**: the OpenAPI spec, the task requirements, real responses of the environment. Never invent endpoints, fields, status codes or error texts: if the data is missing, ask or check with a request to the environment.
3. **Language** of steps, titles, docstrings and messages follows the project; in a new project ask once (default: English).
4. **A new test:** model → client method → step → assertion (+ schema) → fixture → test → marker in `pytest.ini` → `pytest --collect-only -q -m <marker>` → `ruff check .` if the project has the layer rules → a run of **only the new tests** by node id (`pytest --env=<env> tests/<domain>/<file>_test.py::<test>`) → the checklist at the end. Ask before the first run if the environment is shared and you do not know whether creating data there is fine. Never run the whole suite or global triggers to check one test.

## A project built differently

The rules matter more than the file names. Map them onto what the project has:

| The skill says | In a project without this core |
|---|---|
| `HttpClient`, service clients | the project's HTTP wrapper; if tests call `requests` directly, add a thin client for the endpoint you cover and stop there |
| `assert_*` in `asserts/` | the project's assertion helpers; if there are none, put functions next to the domain's steps and keep failed (AssertionError) apart from broken |
| Allure steps and attachments | the project's reporting; without Allure, keep the step structure as functions and logging |
| `wait_until` | the project's waiter (tenacity, polling helpers); never a bare `time.sleep` loop |
| `cfg`, `config.yml` profiles | the project's settings object and secret storage |

Do not migrate a project to this structure as a side effect of writing a test. Propose it separately.

## Layers

```
models/<domain>/                 dataclass models of request bodies + data factories
modules/<domain>/*_client_v1.py  client: 1 method = 1 endpoint, no logic or checks
modules/<domain>/*_test_steps.py steps: business actions, Allure steps, waiting, entity state
tests/<domain>/*_test.py         test: data → steps → assert_*
asserts/<domain>/*_asserts.py    assertions (+ asserts/jsonschemas/)
modules/*.py, conftest.py        the core (pytest-integration-bootstrap skill)
```

| Layer | May use | May not |
|---|---|---|
| test | steps, assertions, model factories, fixtures, `mutate` | clients, `requests`, `allure.attach`, `assert`, `if`/`for`/`sleep`/`try` |
| steps | clients, models, assertions (for preconditions), `wait_until` | `requests`, `allure.attach` |
| client | `HttpClient`, `get_auth` | `allure.step`, `assert`, business logic |
| assertions | `allure_helper`, schemas | clients, steps |

Why: when the API changes, one client changes; when the scenario changes, the steps change. The test stays readable and the report looks the same in every test. In a project scaffolded by the bootstrap skill `ruff check .` enforces part of this (`assert`, `requests`, `time.sleep`, `allure.attach` in the wrong layer).

What the core provides (in another project look for equivalents):

| Module | Use |
|---|---|
| `modules/http_client.py` | `HttpClient(base_url, auth, timeout, verify)`; `get/post/put/patch/delete(route, json=, params=, files=, headers=, url=, attach=)`; attaches the request and the response to Allure itself |
| `modules/auth.py` | `get_auth(cfg, "<profile>")`: profiles in `config.yml` (oauth2, basic, api_key), the token is cached and refreshed; `None` = no authorization |
| `modules/allure_helper.py` | `attach_json`, `attach_text`, `attach_lines`, `attach_png`, `attach_file`; secrets are masked |
| `modules/waiters.py` | `wait_until(probe, until=..., description=..., timeout=, interval=)` |
| `modules/helper.py` | `unique()`, `iso_now()`, `as_instant`, `to_dict(model)`, `file_for_upload(name)`, `mutate(path[, value])`, `fake` (Faker) |
| `modules/errors.py` | `EnvironmentUnavailable`, `AuthError`, `WaitTimeout`: the report categories match these classes |
| `asserts/base_assert.py` | `assert_status`, `json_body`, `field`, `assert_json_schema`, `assert_fields_match`, `assert_contains_item`, `assert_error` |
| `conftest.py` | `--env`, the `cfg` fixture, `item.rep_<phase>`, environment and categories in Allure |

## Structure and names

```
tests/files/           files for uploads
tests/<domain>/        conftest.py (domain fixtures) + *_test.py, __init__.py in every folder
```

- Files: `<domain>_client_v1.py`, `<domain>_test_steps.py`, `<domain>_asserts.py`, `<domain>_schemas.py`, `<scenario>_test.py` (or `test_*.py`: one scheme per project).
- Classes follow PEP 8: `ContractClientV1`, `ContractSteps`. Client methods are `<http method>_<resource>`: `post_contract`, `get_contract`.
- Fixtures that create data start with `f_` (`f_contract`), infrastructure ones do not (`cfg`, `page`). Domain fixtures go to `tests/<domain>/conftest.py`. If the project uses `f_<domain>.py` + `pytest_plugins`, follow the project.

## Test

```python
# tests/contracts/contract_create_test.py
"""Contract creation: POST /contracts, a successful creation and body validation (PROJ-123)."""
import allure
import pytest

from asserts.contracts.contract_asserts import assert_contract_created, assert_contract_saved, assert_validation_error
from modules.contracts.contract_test_steps import ContractSteps
from modules.helper import mutate

pytestmark = [pytest.mark.contracts, allure.epic("Contracts"), allure.feature("Contract creation")]


@allure.story("Successful creation")
@allure.title("A created contract is saved as sent")
def test_create_contract_saves_fields(cfg, f_cleanup):
    """GET /contracts/{id} returns the created contract with the same fields as in the request."""
    contract = ContractSteps(cfg, plan="premium", termMonths=24)
    f_cleanup(contract)

    assert_contract_created(contract.try_create())
    assert_contract_saved(contract.get(), contract.model)


@allure.story("Validation")
@allure.title("Contract creation: {param_id} -> 400")
@pytest.mark.parametrize("change, field", [
    pytest.param(mutate("number"), "number", id="no number"),
    pytest.param(mutate("planId", "not-a-uuid"), "planId", id="planId is not a UUID"),
    pytest.param(mutate("customer.lastName", ""), "lastName", id="empty customer last name"),
])
def test_create_contract_validation(cfg, f_cleanup, change, field):
    """An invalid body is rejected with 400 and an error for the field."""
    contract = ContractSteps(cfg)
    f_cleanup(contract)  # if the product wrongly accepts the body, the contract is still deleted

    response = contract.try_create(body=change(contract.body()))

    assert_validation_error(response, field)
```

- One test = one scenario; arrange / act / assert are separated by an empty line; comments explain only "why".
- A docstring is required: what is checked and why (allure-pytest shows it as the description).
- `@allure.title` on every test; in parametrization use `{param_id}` or `{parameter_name}`; `allure.dynamic.title()` only for computed titles. Parameter ids are human-readable.
- Module `pytestmark`: the domain marker (registered in `pytest.ini`, otherwise CI cannot select it) + `epic` + `feature`; the test has a `story`. A task link: `@allure.issue("PROJ-123")` + `--allure-link-pattern=issue:https://<tracker>/browse/{}`.
- **Never invent `@allure.id`.** In Allure TestOps it links the result to an existing test case; an invented id corrupts that link. Add it only with an id the user gave you or one already in the project; a new test goes without it.
- Negative cases: a valid body + one mutation per case: `mutate("a.b")` removes the key, `mutate("a.b", value)` sets a value. Its repr is shown in the Allure parameters.
- A test has no `assert`, branches, loops, `sleep`, HTTP or `r.json()[...]`: an assertion returns the value the test needs (`assert_contract_created` → id).
- Do not comment out assertions: a known bug gets `pytest.mark.xfail(reason="PROJ-456: ...")`; with `xfail_strict = true` the test reports when the bug is fixed.

## Steps

A steps object = one entity of the test: its model, id and client. The client is a field, not a parent class: a test cannot reach an endpoint directly.

```python
# modules/contracts/contract_test_steps.py
"""Business actions with a contract. One object = one contract of the test."""
import allure

from asserts.base_assert import assert_status
from asserts.contracts.contract_asserts import assert_contract_created
from models.contracts.contract_model import contract_model
from modules.contracts.contract_client_v1 import ContractClientV1
from modules.helper import file_for_upload, to_dict
from modules.waiters import wait_until


class ContractSteps:
    def __init__(self, cfg: dict, plan: str = "basic", **fields):
        self.cfg = cfg
        self.client = ContractClientV1(cfg)
        self.model = contract_model(cfg, plan, **fields)
        self.contract_id: str | None = None

    def __str__(self):
        return f"contract {self.number}"

    @property
    def number(self) -> str:
        return self.model.number

    @property
    def id(self) -> str:
        if self.contract_id is None:
            raise RuntimeError("The contract is not created yet: call create() first")
        return self.contract_id

    def body(self) -> dict:
        """The body from the current model: a fresh copy that may be mutated."""
        return to_dict(self.model)

    # actions under test: the raw response, no checks
    def try_create(self, body: dict | None = None):
        with allure.step(f"Creating {self}"):
            r = self.client.post_contract(self.body() if body is None else body)
            if r.status_code == 201:
                self.contract_id = _id_from(r)  # never KeyError here: the assertion reports a missing id
            return r

    def get(self):
        with allure.step(f"Getting {self}"):
            return self.client.get_contract(self.id)

    def try_submit(self):
        with allure.step(f"Submitting {self}"):
            return self.client.post_submit(self.id)

    # preconditions: check themselves and fail here with a clear reason
    def create(self) -> "ContractSteps":
        self.contract_id = assert_contract_created(self.try_create())
        return self

    def attach_document(self, filename: str) -> "ContractSteps":
        with allure.step(f"Attaching {filename} to {self}"):
            r = self.client.post_document(self.id, file_for_upload(filename))
        assert_status(r, 201, f"Uploading {filename}")
        return self

    def wait_status(self, status: str, timeout: float = 60):
        """Wait for the status; return the last response of GET /contracts/{id}."""
        return wait_until(lambda: self.client.get_contract(self.id),
                          until=lambda r: r.status_code == 200 and _json(r).get("status") == status,
                          description=f"{self} in status {status}", timeout=timeout)

    def delete(self):
        """Postcondition: nothing to do if the contract was never created."""
        if self.contract_id is None:
            return
        with allure.step(f"Deleting {self}"):
            assert_status(self.client.delete_contract(self.contract_id), 204, "Contract deletion")


def _json(response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _id_from(response) -> str | None:
    return _json(response).get("id")
```

- Two methods per action: `try_<action>()` when the action is what the test checks (return the Response, update the state on success); `<action>()` as a precondition (checked by a function from `asserts/`, returns `self` or a useful value). The same step serves positive and negative tests.
- Steps never index into a response (`r.json()["id"]`): the product may answer anything, and a KeyError turns a product defect into a "broken test". Read defensively and let the assertion report what is missing.
- Every business action is `with allure.step(f"...")` in the present continuous: "Creating", "Submitting", "Waiting". Values go in through an f-string: `@allure.step("... {arg}")` inserts a quoted `repr` and cannot do `{self.x}`.
- Product variants are data (config + model factory), not a subclass per variant. A subclass only if the variant has its own actions.
- Waiting only through `wait_until`: one report step, the polling history, the last response. Several services in a scenario: several clients in the steps; steps of one domain may use steps of another.
- A steps class over ~500 lines gets split by scenario (`contract_payment_test_steps.py` ...).

## Client

```python
# modules/contracts/contract_client_v1.py
"""Contracts API client: one method = one endpoint, no logic and no checks. OpenAPI: <link>."""
from modules.auth import get_auth
from modules.http_client import HttpClient


class ContractClientV1(HttpClient):
    def __init__(self, cfg: dict, auth_profile: str | None = "contracts_admin"):
        super().__init__(cfg["urls"]["contracts"], auth=get_auth(cfg, auth_profile),
                         timeout=cfg.get("http_timeout", 30), verify=cfg.get("verify_ssl", True))

    def post_contract(self, body: dict):
        """POST /contracts: create a contract."""
        return self.post("contracts", json=body)

    def get_contract(self, contract_id: str):
        """GET /contracts/{id}: a contract by id."""
        return self.get(f"contracts/{contract_id}")

    def post_document(self, contract_id: str, files: dict):
        """POST /contracts/{id}/documents: attach a file (multipart)."""
        return self.post(f"contracts/{contract_id}/documents", files=files)

    def post_submit(self, contract_id: str):
        """POST /contracts/{id}/submit: submit the contract for approval."""
        return self.post(f"contracts/{contract_id}/submit")

    def delete_contract(self, contract_id: str):
        """DELETE /contracts/{id}: delete a contract."""
        return self.delete(f"contracts/{contract_id}")
```

- A method returns `requests.Response` and neither checks nor parses it; the body is a dict (`json=`), not a JSON string.
- Another role: `auth_profile`; no authorization: `ContractClientV1(cfg, auth_profile=None)`; without the header for one call: `headers={"Authorization": None}` (an empty string sends an empty header, which is a different case); another host or a link from a response: `url=`.
- File downloads and large bodies: `attach=False`; the step attaches the needed file itself (`attach_file`).
- 502/503/504 are retried only for GET/HEAD/OPTIONS. If an endpoint's PUT or DELETE is truly idempotent, give its client its own `Retry` (`HttpClient(..., retry=...)`).

## Models

```python
# models/contracts/contract_model.py
"""Contract creation body. Field names are the API names (camelCase): to_dict() gives JSON ready to send."""
from dataclasses import dataclass, field

from modules.helper import fake, iso_now, unique


@dataclass
class Customer:
    firstName: str = field(default_factory=fake.first_name)
    lastName: str = field(default_factory=fake.last_name)
    email: str = field(default_factory=lambda: f"{unique('autotest')}@example.com")


@dataclass
class ContractModel:
    number: str = field(default_factory=lambda: unique("AT"))
    title: str = field(default_factory=fake.catch_phrase)
    signedAt: str = field(default_factory=iso_now)  # not iso_now(): the value would be computed once, at import
    planId: str | None = None
    termMonths: int = 12
    customer: Customer = field(default_factory=Customer)


def contract_model(cfg: dict, plan: str = "basic", **fields) -> ContractModel:
    """Plan ids come from config.yml of the environment; a typo in a field name raises TypeError."""
    return ContractModel(planId=cfg["plans"][plan]["planId"], **fields)
```

- Field types are JSON-compatible (timestamps as ISO strings); `to_dict()` does not send `None` fields; "the field is missing / null" is checked with a body mutation.
- Everything random or time-dependent goes only through `default_factory`. Uniqueness: `unique()`/uuid; data: Faker in the project's locale (`FAKER_LOCALE`); identifiers with a checksum (tax ids, IBAN, national ids): Faker providers, not random digits.

## Assertions

```python
# asserts/contracts/contract_asserts.py
"""Contract assertions."""
from asserts.base_assert import assert_error, assert_fields_match, assert_json_schema, assert_status, json_body
from asserts.jsonschemas.contract_schemas import CONTRACT, CREATE_CONTRACT_RESPONSE
from modules.helper import as_instant


def assert_contract_created(response) -> str:
    """201 and a body matching the schema; returns the contract id."""
    assert_status(response, 201, "Contract creation")
    body = json_body(response, "Contract creation")
    assert_json_schema(body, CREATE_CONTRACT_RESPONSE, "contract creation response")
    return body["id"]  # safe: the schema requires id


def assert_contract_saved(response, model):
    """200, the schema, and the fields as sent; the server may reformat timestamps."""
    assert_status(response, 200, "Getting the contract")
    body = json_body(response, "Getting the contract")
    assert_json_schema(body, CONTRACT, "contract")
    assert_fields_match(body, model, "contract fields", normalize={"signedAt": as_instant})


def assert_validation_error(response, field: str):
    assert_error(response, 400, {"field": field}, action="Invalid contract rejected")


def assert_submit_success(response):
    assert_status(response, 200, "Contract submission")
    assert_fields_match(json_body(response, "Contract submission"), {"status": "SUBMITTED"}, "submission result")


def assert_submit_rejected(response, message: str):
    assert_error(response, 400, {"field": "documents", "message": message, "critical": True},
                 action="Contract submission rejected")
```

```python
# asserts/jsonschemas/contract_schemas.py
"""JSON schemas of the contracts API; the source is components/schemas in the OpenAPI spec ($ref expanded)."""
CREATE_CONTRACT_RESPONSE = {
    "type": "object",
    "required": ["id", "status", "errors"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "status": {"enum": ["PENDING"]},
        "errors": {"type": "array", "maxItems": 0},
    },
}

CONTRACT = {
    "type": "object",
    "required": ["id", "number", "status", "planId", "customer"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "number": {"type": "string", "minLength": 1},
        "status": {"enum": ["PENDING", "ACTIVE", "SUBMITTED"]},
        "planId": {"type": "string", "format": "uuid"},
        "customer": {"type": "object", "required": ["firstName", "lastName"]},
    },
}
```

- An assertion is an `assert_<what>` function: it opens a "Checking ..." step, its message holds expected / actual / the start of the response. It may return a parsed value so that the test never touches `r.json()`.
- Order: status → structure (JSON Schema) → values. Read the body with `json_body()` and nested values with `field()`: a non-JSON body or a missing field is then a product defect (failed), not a KeyError (broken).
- Money as `Decimal` (`json.loads(r.text, parse_float=Decimal)`). Timestamps are compared through a normalizer (`normalize={"signedAt": as_instant}`): servers often cut microseconds or write `+00:00` instead of `Z`.
- Schemas are dicts in `asserts/jsonschemas/<domain>_schemas.py`, taken from `components/schemas` of the spec (`$ref` expanded); `required` as in the contract; `additionalProperties: false` only if the contract guarantees it. `format: uuid` is checked out of the box; `date-time`, `email` and `uri` need `jsonschema[format]` installed, otherwise they are silently skipped.
- `AssertionError` = a product defect (failed). Do not turn environment or test-code errors into `AssertionError`, and do not let product answers raise anything else: the report categories rely on failed vs broken. 502/503/504 raise `EnvironmentUnavailable` from `assert_status` (broken, "Environment unavailable").

## Fixtures and parallel runs

- Every test is independent: its own data, no global state, no order. `-n 4` gives the same result as a run without it.
- `cfg` is a session fixture (one per worker), read-only: a test that needs other settings builds a copy (`{**cfg, "urls": {...}}`).
- An expensive precondition is a session fixture that performs all actions at once and returns the results; the tests check one each. Tests sharing it get `pytest.mark.xdist_group("<name>")` (+ `--dist loadgroup`), otherwise every worker creates its own copy. The shared entity is read-only: a test that changes it gets its own. The fixture deletes what it created after `yield`.
- What a test creates is deleted by the registry fixture, even if the test failed, and negative tests register it too (the product may wrongly accept the body). A deletion error goes to an attachment and does not hide the result. If the API has no deletion, unique data is enough. Do not run global triggers ("recalculate everything on the environment") in parallel runs.

```python
# tests/contracts/conftest.py
"""Fixtures of the contracts domain."""
import pytest

from modules.allure_helper import attach_text
from modules.contracts.contract_test_steps import ContractSteps


def _delete_quietly(entity):
    """A failed deletion goes to an attachment and does not hide the test result."""
    try:
        entity.delete()
    except Exception as error:  # noqa: BLE001 - cleanup must not fail the test
        attach_text(repr(error), f"Postcondition: {entity} was not deleted")


@pytest.fixture(scope="session")
def f_submission_chain(cfg):
    """One contract for the submission checks: without documents -> upload a document -> success."""
    contract = ContractSteps(cfg).create()
    without_documents = contract.try_submit()
    contract.attach_document("document.pdf")
    yield {"contract": contract, "without_documents": without_documents, "success": contract.try_submit()}
    _delete_quietly(contract)


@pytest.fixture
def f_cleanup():
    """The test registers what it creates: f_cleanup(entity); entity.delete() is called after the test."""
    created = []
    yield created.append
    for entity in reversed(created):
        _delete_quietly(entity)
```

## Allure: what the report must look like

- Hierarchy: `epic` (system/service) → `feature` (function/endpoint) → `story` (scenario) → `title`.
- Steps are business actions from the steps layer and "Checking ..." from assertions. Inside a step an HTTP call has two attachments from `HttpClient`: "POST to <url>" (the request body) and "Response with status code N (t s)" (the response body, plus `X-Request-Id` and similar ids for finding the logs). Secrets are masked in attachments and assertion messages.
- Waiting is one "Waiting: ..." step with the polling history and the last response, not a step per attempt.
- Categories: Environment unavailable → Timed out waiting for a state → Product defects (failed) → Test defects (broken).
- Attachments only through `allure_helper`. One import style: `import allure`.
- Locally: `pytest --env=<env> -m <marker> -n 4 --alluredir allure-results` → `allure serve allure-results`.

## UI and Kafka

- UI tests with Playwright (page objects, locators, `expect` assertions): read [references/ui.md](references/ui.md).
- Asynchronous events in Kafka (a listener before the action, sending events): read [references/kafka.md](references/kafka.md).

## Investigating a failed or flaky test

1. Start from the Allure category and the message, not from the code: "Environment unavailable" and "Test defects" are not product bugs; "Product defects" shows expected / actual / the response; "Timed out" shows the polling history. Take the `X-Request-Id` from the response attachment to find the service logs.
2. Reproduce the single test by node id. If it passes alone but fails in the suite, it depends on order or shared state: run `-p no:randomly` vs `-p randomly` if pytest-randomly is installed, or run the neighbours of its worker.
3. Reproduce in parallel: `-n 4`, then repeat (`pytest-repeat`: `--count 20 -x`). Typical causes: a shared session fixture that a test mutates, a missing `xdist_group`, non-unique data, a fixed time or date computed at import, a waiting time too short for the environment, a global trigger.
4. Fix the cause in the layer it belongs to (data in the model, waiting in the steps, isolation in the fixture). Do not add `sleep`, retries of the whole test or a wider `except`: they hide the next real failure.

## Checklist before handing over

- [ ] The test is independent: its own data, passes alone and with `-n 4`.
- [ ] The test has only steps and `assert_*`: no `assert`, `if`/`for`/`sleep`, HTTP, `r.json()[...]`.
- [ ] Docstring, `@allure.title`, `story`; the module has a marker + `epic` + `feature`; the marker is in `pytest.ini`; no invented `@allure.id`.
- [ ] A new endpoint has a client method with the docstring "METHOD /path: what it does".
- [ ] Preconditions fail in the step with a clear reason; the action under test goes through `try_*`; steps never index into a response.
- [ ] Assertions: status → schema → values through `json_body`/`field`; timestamps normalized; the message is "expected / actual / response".
- [ ] Asynchrony through `wait_until`; created data is deleted (`f_cleanup`, also in negative tests) or unique; a shared fixture is not mutated and cleans up after itself.
- [ ] No secrets in code, config or scripts; a new variable is in `.env.example`.
- [ ] `pytest --collect-only -q -m <marker>` and `ruff check .` pass; the new tests ran against the environment (if there is none, say so); the report opens and reads well.

## What not to do

- A dynamic value as a field default without `default_factory`: it is computed once, at import.
- Own waiting loops and `time.sleep`: different semantics in every file and noise in the report.
- `except: pass`, `print` instead of `logging`, swallowed exceptions: they hide the cause of a failure.
- Fixtures in mixin classes that tests inherit: fixtures belong in conftest or a plugin.
- A subclass per product variant just for other data; steps classes of thousands of lines.
- Hosts, logins and passwords in code and run scripts.
- Commented-out assertions instead of `xfail` with a task number.
- Calling a client or `requests` from a test "just this once": the report and the rules fall apart from the first exception.
