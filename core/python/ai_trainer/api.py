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
from .cues import workout_cues
from .diet_view import diet_options, diet_preview, diet_view
from .equipment import load_steps, plate_load
from .errors import DomainError
from .foods import search as search_foods
from .migrations import migrate_state
from .nutrition import scale_nutrients
from .progress import progress_summary
from .rings import muscle_rings
from .rules.eligibility import decide
from .rules.program import initial_program
from .rules.week_program import option_summaries, week_options
from .spoken_sets import read_set
from .today import today_status

JSON = dict[str, Any]

VERSION = "1.0"


def dispatch_json(raw: str) -> str:
    """Parse, dispatch and serialize. Never raises; every failure is a typed error envelope.

    Malformed payloads come back as ``invalid``. Anything else unexpected comes back as
    ``internal`` instead of escaping into the C bridge; the host saved nothing either way.
    """
    try:
        envelope = json.loads(raw, parse_constant=_reject_non_finite, parse_float=_finite_float)
        result = dispatch(envelope)
        return json.dumps({"schemaVersion": VERSION, "result": result}, allow_nan=False, separators=(",", ":"))
    except DomainError as error:
        return _error(error.code, str(error))
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return _error("invalid", "Invalid contract payload.")
    except Exception:
        return _error("internal", "The training core hit an unexpected error. Nothing was changed.")


def _error(code: str, message: str) -> str:
    return json.dumps({"schemaVersion": VERSION, "error": {"code": code, "message": message}})


def _finite_float(text: str) -> float:
    """Float literals that overflow (``1e999``) become infinity; reject them like NaN."""
    value = float(text)
    if not math.isfinite(value):
        raise DomainError("invalid", "Non-finite values are not supported.")
    return value


def _reject_non_finite(constant: str) -> float:
    """``json`` accepts NaN and Infinity literals by default; the contract never does."""
    raise DomainError("invalid", "Non-finite values are not supported.")


def dispatch(envelope: JSON) -> Any:
    """Validate the envelope and route ``operation`` to its handler."""
    if envelope.get("schemaVersion") != VERSION:
        raise DomainError("unsupported", "Unsupported contract version.")
    contracts.validate(envelope, contracts.REQUEST)
    payload, operation = envelope["payload"], envelope["operation"]

    if operation == "stateCommand":
        return reduce_state(payload, load_library(payload["permitsFixtures"]))
    if operation == "decide":
        return decide(payload["state"], payload["request"], load_library(payload["permitsFixtures"]), payload["now"])
    if operation == "initialProgram":
        library = load_library(payload["permitsFixtures"])
        return initial_program(payload["profile"], library, payload["now"], payload["ids"], payload.get("optionID"))
    if operation == "weekOptions":
        library = load_library(payload["permitsFixtures"])
        if "planner" not in library:
            return []
        return option_summaries(week_options(payload["profile"], library), library)
    if operation == "library":
        return public_library(load_library(payload["permitsFixtures"]))
    if operation == "migrateState":
        return migrate_state(payload["state"])
    if operation == "nutrients":
        return scale_nutrients(payload["nutrients"], payload.get("servings", 1))
    if operation == "recovery":
        return _assess_recovery(payload["observations"])
    if operation == "views":
        library = load_library(payload["permitsFixtures"])
        state, now = payload["state"], payload["now"]
        return {
            "today": today_status(state, library, now, payload.get("utcOffset")),
            "progress": progress_summary(state, library, now),
            "diet": diet_view(state, now, payload.get("dayStart")),
            **_rings(state, library, now, payload),
        }
    if operation == "loadSteps":
        return load_steps(payload["base"], payload["step"])
    if operation == "workoutCues":
        return workout_cues(payload["state"], load_library(payload["permitsFixtures"]), payload["now"]) or {}
    if operation == "plateLoad":
        return plate_load(payload["load"], payload["bar"], payload["plates"])
    if operation == "dietOptions":
        return diet_options()
    if operation == "dietPreview":
        return diet_preview(payload["state"], payload["profile"], payload["now"])
    if operation == "foods":
        return search_foods(payload["query"], payload.get("pattern"), payload["limit"])
    if operation == "readSet":
        library = load_library(payload["permitsFixtures"])
        return read_set(payload["state"], payload["text"], payload["draft"], library)
    raise DomainError("unsupported", "Unknown operation.")


def _rings(state: JSON, library: JSON, now: float, payload: JSON) -> JSON:
    """``{"rings": ...}`` when this week's muscle rings can be counted (ADR-020), else nothing."""
    rings = muscle_rings(state, library, now, payload.get("dayStart"), payload.get("utcOffset"))
    return {} if rings is None else {"rings": rings}


def _assess_recovery(observations: list[JSON]) -> JSON:
    """No reviewed readiness policy exists, so observations can never establish clearance."""
    return {"status": "unassessed", "reason": "NO_REVIEWED_RECOVERY_POLICY", "observations": observations}
