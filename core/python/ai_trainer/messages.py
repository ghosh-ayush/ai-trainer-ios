"""Decision reason codes and their user-facing explanations.

``decisions.json`` maps each reason code to ``[outcome, explanation]``. Keeping
copy in data (not code) lets product edit wording without touching rules and
keeps every rule module free of prose.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Decision = dict[str, Any]

_MESSAGES_PATH = Path(__file__).with_name("decisions.json")
MESSAGES: dict[str, tuple[str, str]] = {
    reason: (outcome, text) for reason, (outcome, text) in json.loads(_MESSAGES_PATH.read_text()).items()
}


def decision(
    reason: str,
    after: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    explanation: str | None = None,
    week: dict[str, Any] | None = None,
) -> Decision:
    """Build a Decision record for ``reason``.

    ``after`` is the proposed plan (only for ``proposeChange`` outcomes);
    ``evidence`` lists the set-log ids/revisions the decision relied on;
    ``week`` is the proposed week of a replan (ADR-018), which holds no ids.
    """
    outcome, default_text = MESSAGES[reason]
    result: Decision = {
        "outcome": outcome,
        "reason": reason,
        "explanation": explanation or default_text,
        "evidence": evidence or [],
    }
    if after is not None:
        result["after"] = after
    if week is not None:
        result["week"] = week
    return result
