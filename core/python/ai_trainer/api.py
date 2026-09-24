"""Contract v1.0 entry point. JSON in, JSON out, no side effects.

``dispatch_json`` is what the Swift host calls through the C bridge. Every
request is validated against the bundled schema before any rule runs; failures
come back as ``{"schemaVersion": "1.0", "error": {"code", "message"}}``.

The host never sends training content. Operations that need it pass
``permitsFixtures`` and the core loads its own bundled library.
"""

from __future__ import annotations

import json
import math
from typing import Any

from . import contracts
from .commands import reduce_state
from .content import load_library, public_library
from .equipment import load_steps
from .errors import DomainError
from .migrations import migrate_state
from .nutrition import scale_nutrients
from .progress import progress_summary
from .rules.eligibility import decide
from .rules.program import initial_program
from .today import today_status

JSON = dict[str, Any]

VERSION = "1.0"


def dispatch_json(raw: str) -> str:
    """Parse, dispatch and serialize. Never raises; every failure is a typed error envelope."""
    try:
        envelope = json.loads(raw)
        result = dispatch(envelope)
        return json.dumps({"schemaVersion": VERSION, "result": result}, allow_nan=False, separators=(",", ":"))
    except DomainError as error:
        return json.dumps({"schemaVersion": VERSION, "error": {"code": error.code, "message": str(error)}})
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return json.dumps(
            {"schemaVersion": VERSION, "error": {"code": "invalid", "message": "Invalid contract payload."}}
        )


def dispatch(envelope: JSON) -> Any:
    """Validate the envelope and route ``operation`` to its handler."""
    if envelope.get("schemaVersion") != VERSION:
        raise DomainError("unsupported", "Unsupported contract version.")
    contracts.validate(envelope, contracts.REQUEST)
    payload, operation = envelope["payload"], envelope["operation"]
    _reject_non_finite_numbers(payload)

    if operation == "stateCommand":
        return reduce_state(payload, load_library(payload["permitsFixtures"]))
    if operation == "decide":
        return decide(payload["state"], payload["request"], load_library(payload["permitsFixtures"]), payload["now"])
    if operation == "initialProgram":
        library = load_library(payload["permitsFixtures"])
        return initial_program(payload["profile"], library, payload["now"], payload["ids"])
    if operation == "library":
        return public_library(load_library(payload["permitsFixtures"]))
    if operation == "migrateState":
        return migrate_state(payload["state"])
    if operation == "nutrients":
        return scale_nutrients(payload["nutrients"], payload.get("servings", 1))
    if operation == "recovery":
        return _assess_recovery(payload["observations"])
    if operation == "todayStatus":
        return today_status(payload["state"], load_library(payload["permitsFixtures"]), payload["now"])
    if operation == "progress":
        return progress_summary(payload["state"], load_library(payload["permitsFixtures"]), payload["now"])
    if operation == "loadSteps":
        return load_steps(payload["base"], payload["step"])
    raise DomainError("unsupported", "Unknown operation.")


def _assess_recovery(observations: list[JSON]) -> JSON:
    """No reviewed readiness policy exists, so observations can never establish clearance."""
    return {"status": "unassessed", "reason": "NO_REVIEWED_RECOVERY_POLICY", "observations": observations}


def _reject_non_finite_numbers(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise DomainError("invalid", "Non-finite values are not supported.")
    if isinstance(value, dict):
        for item in value.values():
            _reject_non_finite_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _reject_non_finite_numbers(item)
