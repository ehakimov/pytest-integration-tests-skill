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
