"""Contract v1.0 entry point. JSON in, JSON out, no side effects.

``dispatch_json`` is what the Swift host calls through the C bridge
(``ai_trainer.service.dispatch_json`` remains as an alias for compatibility).
Every request is validated against the bundled schema before any rule runs;
failures come back as ``{"schemaVersion": "1.0", "error": {"code", "message"}}``.
"""

from __future__ import annotations

import json
import math
from typing import Any

from . import contracts
from .commands import reduce_state
from .commands.workout import validate_set
from .errors import DomainError
from .nutrition import scale_nutrients
from .queries import comparable_sessions, working_logs
from .recommendations import handle_recommendation
from .rules.eligibility import decide
from .rules.program import initial_program
from .rules.progression import propose_progression

JSON = dict[str, Any]

VERSION = "1.0"
SUPPORTED_STATE_SCHEMA_VERSION = 1


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
    if "state" in payload and payload["state"]["schemaVersion"] != SUPPORTED_STATE_SCHEMA_VERSION:
        raise DomainError("unsupported", "Unsupported state version.")

    if operation == "stateCommand":
        return reduce_state(payload)
    if operation == "validateSet":
        validate_set(payload["log"])
        return True
    if operation == "decide":
        return decide(payload["state"], payload["request"], payload["library"], payload["now"])
    if operation == "progression":
        return propose_progression(
            payload["state"], payload["plan"], payload["slot"], payload["policy"], payload["now"]
        )
    if operation == "initialProgram":
        return initial_program(payload["profile"], payload["library"], payload["now"], payload["ids"])
    if operation == "recommendation":
        return handle_recommendation(payload)
    if operation == "nutrients":
        return scale_nutrients(payload["nutrients"], payload.get("servings", 1))
    if operation == "performance":
        return comparable_sessions(payload["state"], payload["slot"], payload["now"])
    if operation == "workingLogs":
        return working_logs(payload["session"], payload["slot"])
    if operation == "catalog":
        return _validate_catalog(payload["exercises"])
    if operation == "recovery":
        return _assess_recovery(payload["observations"])
    raise DomainError("unsupported", "Unknown operation.")


def _validate_catalog(records: list[JSON]) -> list[JSON]:
    """Descriptive catalog records pass through unchanged; duplicate ids fail closed."""
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise DomainError("invalid", "Duplicate exercise catalog identifiers.")
    return records


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
