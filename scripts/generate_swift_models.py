#!/usr/bin/env python3
"""Generate ``apps/ios/Sources/AITrainerCore/Models.swift`` from ``ai_trainer.contract_spec``.

The output is the Codable data layer only: enums and structs with public memberwise
initialisers whose defaults come from ``contract_spec.SWIFT_MODELS``. Behaviour
(computed properties, convenience initialisers, validation) lives in the hand-written
``Models+Helpers.swift``. Run this after any spec change; CI fails if the file drifts.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core/python"))

from ai_trainer import contract_spec as spec  # noqa: E402

OUTPUT = ROOT / "apps/ios/Sources/AITrainerCore/Models.swift"

HEADER = """\
// GENERATED FILE — do not edit by hand.
// Source of truth: core/python/ai_trainer/contract_spec.py
// Regenerate:      python3 scripts/generate_swift_models.py
//
// Codable records shared with the Python core. Field names and JSON shapes must match
// the v1 contract exactly. Behaviour lives in Models+Helpers.swift.

import Foundation
"""


def swift_type(field: spec.FieldSpec, model: spec.SwiftModel) -> str:
    if field.is_map:
        base = spec.SWIFT_TYPE_NAMES.get(field.type, f"[String: {_named_type(field.element_type)}]")
    elif field.is_array:
        element = _named_type(field.element_type)
        base = f"Set<{element}>" if field.name in model.sets else f"[{element}]"
    else:
        base = _named_type(field.type)
    return base + "?" if field.optional else base


def _named_type(name: str) -> str:
    if name in spec.SWIFT_TYPE_NAMES:
        return spec.SWIFT_TYPE_NAMES[name]
    if name in spec.SWIFT_ENUMS:
        return spec.SWIFT_ENUMS[name][0]
    if name in spec.SWIFT_MODELS:
        return spec.SWIFT_MODELS[name].swift_name
    raise KeyError(f"No Swift type for contract type {name!r}")


def render_enum(name: str, cases: list[str]) -> str:
    swift_name, case_iterable = spec.SWIFT_ENUMS[name]
    conformances = "String, Codable" + (", CaseIterable" if case_iterable else "")
    body = ", ".join(cases)
    return f"public enum {swift_name}: {conformances} {{\n    case {body}\n}}\n"


def render_struct(model: spec.ModelSpec, swift: spec.SwiftModel) -> str:
    conformances = "Codable, Equatable" + (", Identifiable" if swift.identifiable else "")
    lines: list[str] = []
    if model.doc:
        lines.append(f"/// {model.doc}")
    lines.append(f"public struct {swift.swift_name}: {conformances} {{")
    for field in model.fields:
        lines.append(f"    public var {field.name}: {swift_type(field, swift)}")
    lines.append("")
    parameters: list[str] = []
    for field in model.fields:
        parameter = f"{field.name}: {swift_type(field, swift)}"
        default = swift.defaults.get(field.name)
        if default is not None:
            parameter += f" = {default}"
        parameters.append(parameter)
    lines.append("    public init(")
    lines.append(",\n".join(f"        {parameter}" for parameter in parameters))
    lines.append("    ) {")
    for field in model.fields:
        lines.append(f"        self.{field.name} = {field.name}")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render() -> str:
    sections: list[str] = [HEADER, "// MARK: - Enums\n"]
    for name, cases in spec.ENUMS.items():
        sections.append(render_enum(name, cases))
    sections.append("// MARK: - Records\n")
    for model in spec.MODELS:
        if model.name == "Recommendation":
            sections.append(render_struct(spec.request_model(), spec.SWIFT_MODELS["Request"]))
        swift = spec.SWIFT_MODELS.get(model.name)
        if swift is not None:
            sections.append(render_struct(model, swift))
    return "\n".join(sections)


def main() -> None:
    OUTPUT.write_text(render())
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
