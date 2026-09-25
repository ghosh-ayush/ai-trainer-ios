"""Chat answers about pain and time away: pausing guidance, and marking or ending a status.

The app cannot assess pain, so these answers only offer what Today already offers: pausing an
exercise, or a break, illness or injury status that pauses the app's own suggestions (ADR-019).
"""

from __future__ import annotations

from ..athlete_state import active_status
from .actions import action
from .context import DAY, JSON, Answer, ChatContext
from .training import no_lighter_rule
from .vocabulary import BACK_WORDS, LIGHTER_WORDS, STATUS_LABELS, STATUS_WORDS


def pain(context: ChatContext, exercise_id: str | None) -> Answer:
    """Pausing an exercise for pain, marking an injury, and what the app cannot judge."""
    lines = [
        "The app can't assess pain or tell which exercises are safe with it.",
        "Pausing an exercise stops its guidance and pauses a workout in progress. "
        "A different exercise is not assumed safe.",
        "If the pain is severe, getting worse or not settling, get it checked by a clinician.",
    ]
    if context.words & LIGHTER_WORDS:
        lines.append(no_lighter_rule())
    actions: list[JSON] = []
    in_session = {slot["exerciseID"] for slot in context.plan_slots()}
    reading = "Something hurts"
    if exercise_id is not None and exercise_id in in_session:
        name = context.name(exercise_id)
        reading = f"Something hurts ({name})"
        actions.append(action("reportPain", f"Pause {name} for pain", exerciseID=exercise_id))
        actions.append(action("openPain", "Pause a different exercise"))
    else:
        actions.append(action("openPain", "Choose the exercise to pause"))
    status = active_status(context.state, context.now)
    current = status["kind"] if status is not None else None
    if context.words & STATUS_WORDS["sick"] and current != "sick":
        actions.append(action("setStatus", "Mark me sick (pauses suggestions)", status="sick"))
    if current != "injured":
        actions.append(action("setStatus", "Mark me injured (pauses suggestions)", status="injured"))
    return reading, lines, actions, []


def away(context: ChatContext, days: int | None) -> Answer:
    """Marking a break, illness or injury, or ending one."""
    status = active_status(context.state, context.now)
    heard_kinds = [kind for kind, words in STATUS_WORDS.items() if context.words & words]
    kind = heard_kinds[0] if len(heard_kinds) == 1 else None  # "sick or away" names no one kind
    back = bool(context.words & BACK_WORDS)
    if status is not None and (back or kind is None):
        label = STATUS_LABELS[status["kind"]]
        until = f" until {context.day(status['endsAt'])}" if status.get("endsAt") else ""
        lines = [f"You are marked {label}{until}. Tap I'm back to resume the app's suggestions."]
        return "Your current status", lines, [action("endStatus", "I'm back")], []
    if back:
        return "Back from a break", ["You are not marked away, so nothing is paused."], [], []
    explanation = (
        "While you're away the app pauses its own suggestions. Your plan doesn't change, and those days "
        "don't count as missed sessions."
    )
    if kind is None:
        actions = [
            action("setStatus", f"I'm {STATUS_LABELS[option]}", status=option)
            for option in ("onBreak", "sick", "injured")
        ]
        actions.append(action("openStatus", "Choose dates"))
        return "Away or unwell", ["Are you on a break, sick or injured?", explanation], actions, []
    label = STATUS_LABELS[kind]
    ends_at = context.now + days * DAY if days is not None else None
    length = f" for {days} day{'s' if days != 1 else ''}" if days is not None else ""
    until = length or " until I'm back"
    title = f"Mark me {label}{until}"
    actions = [action("setStatus", title, status=kind, endsAt=ends_at), action("openStatus", "Choose other dates")]
    return f"{label.capitalize()}{length}", [explanation], actions, []
