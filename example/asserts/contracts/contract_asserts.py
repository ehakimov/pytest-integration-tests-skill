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
