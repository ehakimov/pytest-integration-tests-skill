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
