"""Upgrade a saved AthleteState file to the current state schema version.

The host hands over the saved JSON untouched; this module upgrades it step by
step and validates the result. A file that cannot be upgraded fails closed and
the host leaves it on disk unchanged.

- v1 → v2: recommendations stored their request in Swift's synthesized enum
  shape (``{"progression": {"_0": slotID}}``); v2 stores the explicit request
  (``{"kind": "progression", "slotID": slotID}``) that ``decide`` consumes.
"""

from __future__ import annotations

from typing import Any

from . import contracts
from .contract_spec import STATE_SCHEMA_VERSION
from .errors import DomainError

JSON = dict[str, Any]

CURRENT_STATE_VERSION = STATE_SCHEMA_VERSION

_V1_REQUEST_FIELDS: dict[str, list[str]] = {
    "progression": ["slotID"],
    "shorten": ["minutes"],
    "substitute": ["slotID", "alternativeID"],
    "reschedule": ["date"],
}


def migrate_state(state: JSON) -> JSON:
    """Return ``state`` at ``CURRENT_STATE_VERSION``, or raise ``DomainError('invalid')``."""
    if not isinstance(state, dict):
        raise DomainError("invalid", "Saved state is not an object.")
    if state.get("schemaVersion") == 1:
        state = _v1_to_v2(state)
    if state.get("schemaVersion") != CURRENT_STATE_VERSION:
        raise DomainError("unsupported", "Saved state was written by a newer app version.")
    contracts.validate(state, contracts.REQUEST["$defs"]["State"])
    return state


def _v1_to_v2(state: JSON) -> JSON:
    for recommendation in state.get("recommendations", []):
        kind, values = next(iter(recommendation["request"].items()))
        fields = _V1_REQUEST_FIELDS[kind]
        recommendation["request"] = {
            "kind": kind,
            **{field: values[f"_{position}"] for position, field in enumerate(fields)},
        }
    state["schemaVersion"] = 2
    return state
