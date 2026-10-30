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
