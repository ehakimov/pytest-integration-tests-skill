"""Contract submission: the document check on one shared contract."""
import allure
import pytest

from asserts.contracts.contract_asserts import assert_submit_rejected, assert_submit_success

pytestmark = [pytest.mark.contracts, pytest.mark.xdist_group("submission_chain"),
              allure.epic("Contracts"), allure.feature("Contract submission")]


@allure.story("Required documents")
@allure.title("Submission without documents is rejected")
def test_submit_without_documents_rejected(f_submission_chain):
    """Without an attached document the submission returns 400 and a critical error for documents."""
    assert_submit_rejected(f_submission_chain["without_documents"], "At least one document is required")


@allure.story("Required documents")
@allure.title("Submission succeeds after a document is uploaded")
def test_submit_after_upload_succeeds(f_submission_chain):
    """Once a document is uploaded, a repeated submission succeeds."""
    assert_submit_success(f_submission_chain["success"])
