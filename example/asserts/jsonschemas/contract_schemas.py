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
