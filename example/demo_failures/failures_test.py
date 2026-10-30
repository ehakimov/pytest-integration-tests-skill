"""
Failures on purpose: how different causes look in Allure and which report category they land in.

Not part of the regular run (outside testpaths). Run:
    pytest demo_failures -n 2 --alluredir allure-results
"""
import allure
import pytest

from asserts.contracts.contract_asserts import assert_contract_created
from asserts.web.web_asserts import assert_text
from modules.contracts.contract_test_steps import ContractSteps
from modules.web.web_test_steps import WebSteps

pytestmark = [allure.epic("Failure demo")]


def _with_url(cfg: dict, url: str) -> dict:
    """A copy of cfg with another contracts URL: cfg itself is shared and read-only."""
    return {**cfg, "urls": {**cfg["urls"], "contracts": url}, "http_timeout": 3}


@allure.title("Product defect: the service rejects a request the test considers valid")
def test_product_defect(cfg):
    """Category "Product defects": "expected 201, got 400" with the method, URL and response body."""
    contract = ContractSteps(cfg, number="")

    assert_contract_created(contract.try_create())


@allure.title("Timeout: the contract does not reach the status")
def test_wait_timeout(cfg):
    """Category "Timed out waiting for a state": the waiting step holds the polling history and the last response."""
    contract = ContractSteps(cfg).create()

    contract.wait_status("APPROVED", timeout=3)


@allure.title("Environment unavailable: no connection")
def test_no_connection(cfg):
    """Category "Environment unavailable": ConnectionError after the retries, the test is broken."""
    ContractSteps(_with_url(cfg, "http://127.0.0.1:9/api/v1")).create()


@allure.title("Environment unavailable: the gateway answers 503")
def test_gateway_unavailable(cfg):
    """Category "Environment unavailable": 503 is not a product defect, the test is broken."""
    ContractSteps(_with_url(cfg, cfg["urls"]["contracts"].replace("/api/v1", "/down/api/v1"))).create()


@allure.title("Broken test: an error in the test data")
def test_broken_test_code(cfg):
    """Category "Test defects": KeyError, the plan is not in config.yml, the test is broken."""
    ContractSteps(cfg, plan="no_such_plan")


@pytest.mark.ui
@allure.title("UI: waiting for the greeting after signing in with a wrong password")
def test_ui_failure_artifacts(page, cfg):
    """A failed UI test gets a screenshot and trace.zip from the page fixture (Tear down in the report)."""
    steps = WebSteps(page, cfg)

    username = steps.login_as("operator", password="wrong-password")

    assert_text(steps.greeting, f"Welcome, {username}", "the greeting")
