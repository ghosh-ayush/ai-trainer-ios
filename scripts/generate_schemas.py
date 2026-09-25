#!/usr/bin/env python3
"""Generate the v1 JSON contracts from ``ai_trainer.contract_spec`` into the Python package.

Run from any directory after changing the spec. CI fails if the committed files drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core/python"))

from ai_trainer import contract_spec as spec  # noqa: E402

Schema = dict[str, Any]


def ref(name: str) -> Schema:
    return {"$ref": "#/$defs/" + name}


def array_of(item: Schema) -> Schema:
    return {"type": "array", "items": item}


def object_of(fields: dict[str, Schema], required: list[str] | None = None) -> Schema:
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields) if required is None else required,
        "additionalProperties": False,
    }


def field_schema(field: spec.FieldSpec) -> Schema:
    if field.is_array:
        schema = array_of(ref(field.element_type))
    elif field.is_map:
        schema = {"type": "object", "additionalProperties": ref(field.element_type)}
    else:
        schema = ref(field.type)
    return {"anyOf": [schema, {"type": "null"}]} if field.optional else schema


def model_schema(model: spec.ModelSpec) -> Schema:
    properties = {field.name: field_schema(field) for field in model.fields}
    required = [field.name for field in model.fields if not field.optional]
    return object_of(properties, required)


def build_definitions() -> dict[str, Schema]:
    definitions: dict[str, Schema] = {}
    for name, json_type in spec.PRIMITIVES.items():
        definitions[name] = {"type": json_type}
    definitions["UUID"] = {"type": "string", "pattern": spec.UUID_PATTERN}
    definitions["Date"] = {"type": "number", "description": spec.DATE_DESCRIPTION}
    for name, values in spec.ENUMS.items():
        definitions[name] = {"type": "string", "enum": values}

    for model in spec.MODELS:
        if model.name == "Session":
            definitions["Omissions"] = {
                "type": "object",
                "additionalProperties": ref("Omission"),
            }
        if model.name == "Recommendation":
            definitions["Request"] = {
                "oneOf": [
                    object_of(
                        {
                            "kind": {"const": kind},
                            **{
                                name.rstrip("?"): field_schema(spec.FieldSpec(name.rstrip("?"), kind_type))
                                for name, kind_type in fields
                            },
                        },
                        required=["kind", *(name for name, _ in fields if not name.endswith("?"))],
                    )
                    for kind, fields in spec.REQUEST_KINDS.items()
                ]
            }
        definitions[model.name] = model_schema(model)

    for model_name, field_name, minimum, maximum in spec.INTEGER_BOUNDS:
        definitions[model_name]["properties"][field_name] = {
            "type": "integer",
            "minimum": minimum,
            "maximum": maximum,
        }
    definitions["State"]["properties"]["schemaVersion"] = {"const": spec.STATE_SCHEMA_VERSION}
    return definitions


def build_request(definitions: dict[str, Schema]) -> Schema:
    operations: dict[str, Schema] = {}
    for name, fields in spec.OPERATIONS:
        definitions[name + "Payload"] = model_schema(spec._model(name + "Payload", fields))
        operations[name] = ref(name + "Payload")

    command_variants: list[Schema] = []
    for name, fields in spec.COMMANDS.items():
        definitions[name + "Arguments"] = model_schema(spec._model(name + "Arguments", fields))
        command_variants.append(
            object_of(
                {
                    "command": {"const": name},
                    "arguments": ref(name + "Arguments"),
                    "state": ref("State"),
                    "permitsFixtures": ref("Bool"),
                    "now": ref("Date"),
                    "ids": array_of(ref("UUID")),
                }
            )
        )
    definitions["stateCommandPayload"] = {"oneOf": command_variants}
    operations["stateCommand"] = ref("stateCommandPayload")

    definitions["initialProgramPayload"]["properties"]["ids"]["minItems"] = spec.MIN_IDS["initialProgram"]
    for variant in command_variants:
        variant["properties"]["ids"]["minItems"] = spec.MIN_IDS["stateCommand"]

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:ai-trainer:core:1.0:request",
        "$defs": definitions,
        "oneOf": [
            object_of(
                {
                    "schemaVersion": {"const": "1.0"},
                    "operation": {"const": name},
                    "payload": payload,
                }
            )
            for name, payload in operations.items()
        ],
    }


def build_response(definitions: dict[str, Schema], request: Schema) -> Schema:
    for model in spec.RESULT_MODELS:
        definitions[model.name] = model_schema(model)
    result_variants = [
        array_of(ref(type_name[1:-1])) if type_name.startswith("[") else ref(type_name)
        for type_name in spec.RESULT_TYPES.values()
    ]
    return {
        "$schema": request["$schema"],
        "$id": "urn:ai-trainer:core:1.0:response",
        "$defs": definitions,
        "oneOf": [
            object_of(
                {
                    "schemaVersion": {"const": "1.0"},
                    "result": {"anyOf": result_variants},
                }
            ),
            object_of({"schemaVersion": {"const": "1.0"}, "error": ref("Error")}),
        ],
    }


def main() -> None:
    definitions = build_definitions()
    request = build_request(definitions)
    response = build_response(definitions, request)  # shares ``definitions`` by reference, as before
    for name, value in (("request", request), ("response", response)):
        text = json.dumps(value, indent=2) + "\n"
        (ROOT / "core/python/ai_trainer" / f"{name}.schema.json").write_text(text)


if __name__ == "__main__":
    main()
