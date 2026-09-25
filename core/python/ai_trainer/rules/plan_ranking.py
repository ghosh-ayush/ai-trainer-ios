"""Order weekly plan candidates for one athlete (ADR-017).

``week_plans`` returns only weeks that keep the evidence guardrails. This module decides which of
them suits this athlete best, from what the app knows about them: goal, weekly target, the splits
they said they like or avoid, and how many sessions a week they have recently completed. Every
candidate gets a score from 0 to 1 per feature and a weighted total. The weights live in the
content bundle as owner decisions; none is set here.

Unknown stays unknown: without recent history or stated preferences those features are neutral,
never assumed favourable. The ranking only orders proposals. The athlete still accepts a plan
(rule 3), and the on-device model may choose among the top candidates but never outside them.

Features:

- ``volume``: how close each trainable major muscle comes to the weekly target (capped at 1).
- ``exposures``: share of major muscles trained on at least the minimum number of sessions a week
  (ACSM26: at least two sessions for strength). The bundle weights it by goal.
- ``recovery``: share of sessions that do not train a muscle the day after it was trained.
- ``spread``: how evenly each major muscle's sessions are spaced around the week: its shortest
  gap against the even gap (7 days divided by its sessions), capped at 1. Mon/Thu scores
  higher than Sat/Mon for the same two sessions.
- ``variety``: share of the bundle's variety roles (for example horizontal and vertical presses
  and pulls, hinge, single-leg) that appear in the week.
- ``adherence``: 1 when the week asks for no more sessions than the athlete recently completed plus
  one, falling off beyond that; neutral (0.5) without history.
- ``preference``: 1 for a split the athlete likes, 0 for one they avoid, 0.5 otherwise.
- ``habit``: share of the week's sessions on weekdays the athlete has actually been training on
  (ADR-018); neutral (0.5) when no such days are known.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

JSON = dict[str, Any]

NEUTRAL = 0.5
# A spread this even (e.g. Mon/Thu for two sessions: 3 of 3.5 days) is worth telling the athlete.
SPREAD_REASON_THRESHOLD = 0.85


def rank_weeks(candidates: list[JSON], athlete: JSON, weekly: JSON, structures: JSON, ranking: JSON) -> list[JSON]:
    """``candidates`` with ``features``, ``score`` and ``reasons`` added, best first.

    ``athlete`` holds ``goal``, ``target``, optional ``likedSplits`` / ``avoidedSplits`` and optional
    ``recentSessionsPerWeek``. ``ranking`` is the bundle's ranking block: ``weights`` per goal
    (feature -> weight), ``varietyRoles`` and ``adherenceSlack``. Ties keep fewer sessions
    first, then the candidate id, so the order is stable.
    """
    weights: dict[str, float] = ranking["weights"][athlete["goal"]]
    scored: list[JSON] = []
    for candidate in candidates:
        features = _features(candidate, athlete, weekly, structures, ranking)
        score = sum(weights.get(name, 0.0) * value for name, value in features.items())
        total_weight = sum(weights.get(name, 0.0) for name in features) or 1.0
        scored.append(
            {
                **candidate,
                "features": features,
                "score": round(score / total_weight, 4),
                "reasons": _reasons(candidate, features),
            }
        )
    scored.sort(key=lambda item: (-item["score"], len(item["sessions"]), item["id"]))
    return scored


def _features(candidate: JSON, athlete: JSON, weekly: JSON, structures: JSON, ranking: JSON) -> dict[str, float]:
    majors = [muscle for muscle in structures["majorMuscles"] if muscle in candidate["weeklySets"]]
    target: float = athlete["target"]
    volume = sum(min(candidate["weeklySets"][muscle] / target, 1.0) for muscle in majors) / max(len(majors), 1)
    minimum_exposures = weekly["strengthExposuresMin"]
    exposed = [muscle for muscle in majors if candidate["exposures"].get(muscle, 0) >= minimum_exposures]
    return {
        "volume": round(volume, 4),
        "exposures": round(len(exposed) / max(len(majors), 1), 4),
        "recovery": _recovery(candidate, structures),
        "spread": _spread(candidate, majors, structures),
        "variety": _variety(candidate, ranking["varietyRoles"]),
        "adherence": _adherence(len(candidate["sessions"]), athlete.get("recentSessionsPerWeek"), ranking),
        "preference": _preference(candidate["split"], athlete),
        "habit": _habit(candidate, athlete.get("habitDays")),
    }


def _recovery(candidate: JSON, structures: JSON) -> float:
    """Share of sessions that train no primary muscle trained the day before (Sunday precedes Monday)."""
    sessions = candidate["sessions"]
    if len(sessions) < 2:
        return 1.0
    trained_by_day = {session["day"]: _primary_muscles_in(session, structures) for session in sessions}
    clear = 0
    for session in sessions:
        day_before = (session["day"] - 1) % 7
        overlap = trained_by_day.get(day_before, set()) & trained_by_day[session["day"]]
        if not overlap:
            clear += 1
    return round(clear / len(sessions), 4)


def _spread(candidate: JSON, majors: list[str], structures: JSON) -> float:
    """Mean over major muscles of (shortest gap between its sessions) / (even gap), capped at 1."""
    if not majors:
        return 1.0
    scores: list[float] = []
    for muscle in majors:
        days = sorted(
            session["day"] for session in candidate["sessions"] if muscle in _primary_muscles_in(session, structures)
        )
        if len(days) < 2:
            scores.append(1.0)
            continue
        gaps = [later - earlier for earlier, later in pairwise(days)]
        gaps.append(days[0] + 7 - days[-1])  # the week repeats
        scores.append(min(min(gaps) / (7 / len(days)), 1.0))
    return round(sum(scores) / len(scores), 4)


def _variety(candidate: JSON, variety_roles: list[str]) -> float:
    present = {slot["role"] for session in candidate["sessions"] for slot in session["slots"]}
    return round(len(present & set(variety_roles)) / max(len(variety_roles), 1), 4)


def _adherence(sessions: int, recent: float | None, ranking: JSON) -> float:
    """1 up to the recent weekly sessions plus the slack, then falling to 0 over three more sessions."""
    if recent is None:
        return NEUTRAL
    slack: float = ranking["adherenceSlack"]
    excess = sessions - (recent + slack)
    if excess <= 0:
        return 1.0
    return round(max(0.0, 1.0 - excess / 3), 4)


def _habit(candidate: JSON, habit_days: list[int] | None) -> float:
    """Share of sessions on the athlete's habitual training days; neutral without any."""
    if not habit_days:
        return NEUTRAL
    on_habit = sum(1 for session in candidate["sessions"] if session["day"] in habit_days)
    return round(on_habit / len(candidate["sessions"]), 4)


def _preference(split: str, athlete: JSON) -> float:
    if split in athlete.get("likedSplits", []):
        return 1.0
    if split in athlete.get("avoidedSplits", []):
        return 0.0
    return NEUTRAL


def _reasons(candidate: JSON, features: dict[str, float]) -> list[str]:
    """Reason codes the app turns into plain explanations."""
    reasons = ["REACHES_WEEKLY_FLOOR" if candidate["volume"] == "full" else "REDUCED_VOLUME_FOR_TIME"]
    if features["exposures"] == 1.0:
        reasons.append("EACH_MUSCLE_TWICE_OR_MORE")
    if features["recovery"] == 1.0:
        reasons.append("NO_MUSCLE_ON_BACK_TO_BACK_DAYS")
    if features["spread"] >= SPREAD_REASON_THRESHOLD:
        reasons.append("SPREAD_ACROSS_THE_WEEK")
    if features["adherence"] == 1.0:
        reasons.append("FITS_RECENT_ROUTINE")
    if features["preference"] == 1.0:
        reasons.append("A_SPLIT_YOU_LIKE")
    if features["habit"] == 1.0:
        reasons.append("ON_THE_DAYS_YOU_TRAIN")
    return reasons


def _primary_muscles_in(session: JSON, structures: JSON) -> set[str]:
    muscles: set[str] = set()
    for slot in session["slots"]:
        for muscle, credit in structures["roles"][slot["role"]]["muscles"].items():
            if credit >= 1:
                muscles.add(muscle)
    return muscles
