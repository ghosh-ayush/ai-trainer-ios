"""Upgrade a saved AthleteState file to the current state schema version.

The host hands over the saved JSON untouched; this module upgrades it step by
step and validates the result. A file that cannot be upgraded fails closed and
the host leaves it on disk unchanged.

- v1 → v2: recommendations stored their request in Swift's synthesized enum
  shape (``{"progression": {"_0": slotID}}``); v2 stores the explicit request
  (``{"kind": "progression", "slotID": slotID}``) that ``decide`` consumes.
- v2 → v3: the diet system (ADR-016) adds weigh-ins, diet decisions and the Apple Health
  weigh-ins the athlete deleted. Older files had none, so all start empty; the optional
  diet profile and targets stay absent.
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
    if state.get("schemaVersion") == 2:
        state = _v2_to_v3(state)
    if state.get("schemaVersion") == 3:
        state = _repair_early_v3(state)
        state = _v3_to_v4(state)
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


def _v2_to_v3(state: JSON) -> JSON:
    state.setdefault("weighIns", [])
    state.setdefault("dietDecisions", [])
    state.setdefault("excludedWeighIns", [])
    state["schemaVersion"] = 3
    return state


def _v3_to_v4(state: JSON) -> JSON:
    """Weekly plans (ADR-017) add optional ``Profile.freeDays``/``minutesByDay`` and ``Plan.weekday``.

    Nothing is filled in: an older profile never said which weekdays are free, so they stay unknown
    until the athlete picks them.
    """
    state["schemaVersion"] = 4
    return state


def _repair_early_v3(state: JSON) -> JSON:
    """Files written by pre-release diet builds: a SCOFF count instead of answers, no deletion list.

    The count is kept as that many "yes" answers, so a positive screen stays positive.
    """
    state.setdefault("excludedWeighIns", [])
    screening = (state.get("dietProfile") or {}).get("screening")
    if screening is not None and "scoffYesCount" in screening:
        count = screening.pop("scoffYesCount")
        screening["scoffAnswers"] = [index < count for index in range(max(count, 5))]
    return state
