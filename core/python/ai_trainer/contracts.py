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


Check = Callable[[Any], bool]


def validate(value: Any, schema: Schema, root: Schema = REQUEST) -> None:
    """Raise ``DomainError('invalid')`` unless ``value`` conforms to ``schema``.

    Each schema is compiled once into plain Python checks and cached, so validating a
    multi-megabyte state does not re-read the schema dictionaries at every node.
    """
    if not _compiled(schema, root)(value):
        _fail()


def _compiled(schema: Schema, root: Schema) -> Check:
    key = (id(root), id(schema))
    check = _CACHE.get(key)
    if check is None:
        compiler = _COMPILERS.get(id(root))
        if compiler is None:
            compiler = _COMPILERS[id(root)] = _Compiler(root)
        check = _CACHE[key] = compiler.compile(schema)
    return check


class _Compiler:
    """Turns one schema root's nodes into closures. ``$defs`` are compiled once and shared."""

    def __init__(self, root: Schema) -> None:
        self.root = root
        self.definitions: dict[str, Check] = {}

    def definition(self, name: str) -> Check:
        if name not in self.definitions:
            # Placeholder first, so a definition that refers to itself resolves lazily.
            self.definitions[name] = lambda value: self.definitions[name](value)
            self.definitions[name] = self.compile(self.root["$defs"][name])
        return self.definitions[name]

    def compile(self, schema: Schema) -> Check:
        if "$ref" in schema:
            return self.definition(schema["$ref"].split("/")[-1])
        checks: list[Check] = []
        for keyword in ("oneOf", "anyOf"):
            if keyword in schema:
                checks.append(
                    _variants([self.compile(variant) for variant in schema[keyword]], exactly_one=keyword == "oneOf")
                )
        if "const" in schema:
            constant = schema["const"]
            checks.append(lambda value: type(value) is type(constant) and value == constant)
        if "enum" in schema:
            allowed = schema["enum"]
            checks.append(lambda value: value in allowed)
        kind = schema.get("type")
        if kind == "object":
            checks.append(self._object(schema))
        elif kind == "array":
            checks.append(self._array(schema))
        elif kind == "string":
            checks.append(_string(schema.get("pattern")))
        elif kind in _SCALAR_CHECKS:
            checks.append(_SCALAR_CHECKS[kind])
        if "minimum" in schema:
            minimum = schema["minimum"]
            checks.append(lambda value: value >= minimum)
        if "maximum" in schema:
            maximum = schema["maximum"]
            checks.append(lambda value: value <= maximum)
        if len(checks) == 1:
            return checks[0]
        return lambda value: all(check(value) for check in checks)

    def _object(self, schema: Schema) -> Check:
        required = tuple(schema.get("required", []))
        properties = {name: self.compile(child) for name, child in schema.get("properties", {}).items()}
        additional = schema.get("additionalProperties")
        extra: Check | None = self.compile(additional) if isinstance(additional, dict) else None
        closed = additional is False

        def check(value: Any) -> bool:
            if not isinstance(value, dict):
                return False
            for name in required:
                if name not in value:
                    return False
            for name, item in value.items():
                child = properties.get(name)
                if child is not None:
                    if not child(item):
                        return False
                elif closed or (extra is not None and not extra(item)):
                    return False
            return True

        return check

    def _array(self, schema: Schema) -> Check:
        minimum = schema.get("minItems", 0)
        item_check = self.compile(schema["items"])

        def check(value: Any) -> bool:
            if not isinstance(value, list) or len(value) < minimum:
                return False
            return all(item_check(item) for item in value)

        return check


def _variants(checks: list[Check], exactly_one: bool) -> Check:
    def check(value: Any) -> bool:
        matches = sum(1 for variant in checks if variant(value))
        return matches == 1 if exactly_one else matches > 0

    return check


def _string(pattern: str | None) -> Check:
    if pattern is None:
        return lambda value: isinstance(value, str)
    compiled = re.compile(pattern)
    return lambda value: isinstance(value, str) and compiled.fullmatch(value) is not None


# Exact-type checks: JSON booleans are not integers, and numbers must be finite.
_SCALAR_CHECKS: dict[str, Check] = {
    "boolean": lambda value: type(value) is bool,
    "integer": lambda value: type(value) is int,
    "number": lambda value: type(value) in (int, float) and math.isfinite(value),
    "null": lambda value: value is None,
}

_CACHE: dict[tuple[int, int], Check] = {}
_COMPILERS: dict[int, _Compiler] = {}


def _fail() -> None:
    raise DomainError("invalid", "Invalid contract payload.")
