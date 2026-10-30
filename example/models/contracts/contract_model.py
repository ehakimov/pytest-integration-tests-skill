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
