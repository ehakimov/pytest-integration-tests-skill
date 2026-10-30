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
