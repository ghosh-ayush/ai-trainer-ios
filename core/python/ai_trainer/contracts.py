"""Offline validator for the deliberately bounded JSON Schema subset used by contract v1.

Supported keywords: ``$ref`` (local ``#/$defs`` only), ``oneOf``, ``anyOf``,
``const``, ``enum``, ``type`` (object/array/string/boolean/integer/number/null),
``properties``, ``required``, ``additionalProperties``, ``items``, ``minItems``,
``pattern``, ``minimum``, ``maximum``. Nothing else is needed and nothing else is
accepted, so the bundled runtime needs no third-party dependency.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import DomainError

Schema = dict[str, Any]

_PACKAGE_DIR = Path(__file__).parent
REQUEST: Schema = json.loads((_PACKAGE_DIR / "request.schema.json").read_text())
RESPONSE: Schema = json.loads((_PACKAGE_DIR / "response.schema.json").read_text())


def validate(value: Any, schema: Schema, root: Schema = REQUEST) -> None:
    """Raise ``DomainError('invalid')`` unless ``value`` conforms to ``schema``."""
    if "$ref" in schema:
        definition_name = schema["$ref"].split("/")[-1]
        validate(value, root["$defs"][definition_name], root)
        return

    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            matches = 0
            for variant in schema[keyword]:
                try:
                    validate(value, variant, root)
                    matches += 1
                except DomainError:
                    pass
            if matches == 0 or (keyword == "oneOf" and matches != 1):
                _fail()

    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        _fail()
    if "enum" in schema and value not in schema["enum"]:
        _fail()

    kind = schema.get("type")
    if kind == "object":
        _validate_object(value, schema, root)
    elif kind == "array":
        _validate_array(value, schema, root)
    elif kind == "string":
        if not isinstance(value, str):
            _fail()
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            _fail()
    elif kind in _SCALAR_CHECKS and not _SCALAR_CHECKS[kind](value):
        _fail()

    if "minimum" in schema and value < schema["minimum"]:
        _fail()
    if "maximum" in schema and value > schema["maximum"]:
        _fail()


# Exact-type checks: JSON booleans are not integers, and numbers must be finite.
_SCALAR_CHECKS: dict[str, Callable[[Any], bool]] = {
    "boolean": lambda value: type(value) is bool,
    "integer": lambda value: type(value) is int,
    "number": lambda value: type(value) in (int, float) and math.isfinite(value),
    "null": lambda value: value is None,
}


def _validate_object(value: Any, schema: Schema, root: Schema) -> None:
    if not isinstance(value, dict) or not all(key in value for key in schema.get("required", [])):
        _fail()
    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties")
    for key, item in value.items():
        if key in properties:
            validate(item, properties[key], root)
        elif additional is False:
            _fail()
        elif isinstance(additional, dict):
            validate(item, additional, root)


def _validate_array(value: Any, schema: Schema, root: Schema) -> None:
    if not isinstance(value, list):
        _fail()
    if len(value) < schema.get("minItems", 0):
        _fail()
    for item in value:
        validate(item, schema["items"], root)


def _fail() -> None:
    raise DomainError("invalid", "Invalid contract payload.")
