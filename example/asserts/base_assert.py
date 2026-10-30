"""Base assertions. Each one is an Allure step with an "expected / actual / response" message.

AssertionError = a product defect (failed). A response the product should not give (non-JSON body, a missing
field) also fails with AssertionError, never with KeyError: failed vs broken is what the report categories use.
"""
import json
from dataclasses import is_dataclass
from functools import lru_cache

import allure
from jsonschema.validators import validator_for

from modules.allure_helper import attach_lines, body_preview, is_secret, mask_secrets
from modules.errors import EnvironmentUnavailable
from modules.helper import to_dict

MAX_BODY = 1000
_MISSING = object()


def assert_status(response, expected: int, action: str = "Request"):
    with allure.step(f"Checking: {action} -> {expected}"):
        if response.status_code == expected:
            return
        message = (f"{action}: expected {expected}, got {response.status_code}. "
                   f"{response.request.method} {response.url}\n{body_preview(response, MAX_BODY)}")
        if response.status_code in (502, 503, 504):
            raise EnvironmentUnavailable(message)  # the gateway answered, not the service: the test could not run
        raise AssertionError(message)


def json_body(response, what: str = "response"):
    """The parsed body; a non-JSON body is a product defect with the start of the body in the message."""
    try:
        return response.json()
    except ValueError:
        raise AssertionError(f"{what}: expected JSON, got {response.headers.get('Content-Type', 'no Content-Type')}. "
                             f"{response.request.method} {response.url}\n{body_preview(response, MAX_BODY)}") from None


def field(data: dict, path: str, what: str = "response"):
    """data["a"]["b"] by the path "a.b"; a missing field is a product defect, not a KeyError."""
    node = data
    for key in path.split("."):
        if isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        elif isinstance(node, dict) and key in node:
            node = node[key]
        else:
            raise AssertionError(f"{what}: no field {path}. Got: {json.dumps(mask_secrets(data), ensure_ascii=False)[:MAX_BODY]}")
    return node


@lru_cache(maxsize=None)
def _validator(schema_json: str):
    schema = json.loads(schema_json)
    cls = validator_for(schema)
    cls.check_schema(schema)  # a typo in the schema ("requried") fails here instead of passing silently
    return cls(schema, format_checker=cls.FORMAT_CHECKER)  # without it "format": "uuid" is not checked


def assert_json_schema(data, schema: dict, name: str):
    """All schema violations at once, with field paths."""
    with allure.step(f"Checking the structure against the schema \"{name}\""):
        validator = _validator(json.dumps(schema, sort_keys=True))
        errors = sorted(validator.iter_errors(data), key=lambda e: e.json_path)
        if errors:
            lines = [f"{e.json_path}: {e.message}" for e in errors]
            attach_lines(lines, f"Schema violations: {name}")
            raise AssertionError(f"The response does not match the schema \"{name}\":\n" + "\n".join(lines[:10]))


def assert_fields_match(actual: dict, expected, name: str = "data", normalize: dict | None = None):
    """The fields of expected (a dataclass or a dict) equal those in actual; the OK/MISMATCH table goes to an attachment.

    expected is compared as sent: to_dict() drops None fields. normalize: {"field": function} for values the
    server may reformat, e.g. {"createdAt": as_instant} for timestamps.
    """
    expected = to_dict(expected) if is_dataclass(expected) else expected
    normalize = normalize or {}
    with allure.step(f"Checking that {name} match what was sent"):
        lines = []
        for key, want in expected.items():
            got = actual.get(key, _MISSING) if isinstance(actual, dict) else _MISSING
            norm = normalize.get(key, lambda v: v)
            shown_want, shown_got = ("***", "***") if is_secret(key) else (repr(want), repr(got))
            if got is _MISSING:
                lines.append(f"MISMATCH  {key}: expected {shown_want}, the field is missing")
            elif norm(got) == norm(want):
                lines.append(f"OK        {key}: {shown_got}")
            else:
                lines.append(f"MISMATCH  {key}: expected {shown_want}, got {shown_got}")
        attach_lines(lines, f"Comparison: {name}")
        mismatches = [line for line in lines if line.startswith("MISMATCH")]
        if mismatches:
            raise AssertionError(f"{name} do not match:\n" + "\n".join(mismatches))


def assert_contains_item(items, expected: dict, where: str = "the list"):
    """There is an element containing all pairs of expected (nested dicts partially); returns it."""
    with allure.step(f"Checking that {where} contains {expected}"):
        if not isinstance(items, list):
            raise AssertionError(f"{where}: expected a list, got {type(items).__name__}")
        for item in items:
            if _contains(item, expected):
                return item
        raise AssertionError(f"{where} has no element with {expected}. Got ({len(items)} items): "
                             f"{json.dumps(mask_secrets(items), ensure_ascii=False)[:MAX_BODY]}")


def assert_error(response, status: int, error: dict, errors_key: str = "errors", action: str = "Request rejected"):
    """status and an element of body[errors_key] containing error. Adapt errors_key to the project's error format
    (RFC 9457 problem+json: errors_key="errors" or "invalid-params", depending on the API)."""
    assert_status(response, status, action)
    return assert_contains_item(field(json_body(response), errors_key), error, errors_key)


def _contains(item, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(item, dict) and all(k in item and _contains(item[k], v) for k, v in expected.items())
    return item == expected
