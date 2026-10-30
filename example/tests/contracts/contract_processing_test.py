"""Asynchronous processing of a contract after creation."""
import allure
import pytest

from modules.contracts.contract_test_steps import ContractSteps

pytestmark = [pytest.mark.contracts, allure.epic("Contracts"), allure.feature("Contract processing")]


@allure.story("Asynchronous processing")
@allure.title("A created contract is processed and becomes ACTIVE")
def test_contract_becomes_active(cfg, f_cleanup):
    """After creation the contract passes the checks and becomes ACTIVE in time.

    The check is the wait itself: if the status does not come, wait_until fails with the polling history.
    """
    contract = ContractSteps(cfg).create()
    f_cleanup(contract)

    contract.wait_status("ACTIVE", timeout=15)
