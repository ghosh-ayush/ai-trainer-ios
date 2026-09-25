"""Chat answers about the research behind the numbers, today's food, and what chat can answer."""

from __future__ import annotations

from ..diet_view import diet_view
from ..wording import join_words
from .actions import STARTERS, action, ask
from .context import Answer, ChatContext
from .training import progression_rule
from .vocabulary import DEFAULT_EVIDENCE, EVIDENCE_ITEMS


def evidence(context: ChatContext) -> Answer:
    """Where the plan's numbers come from: each asked-about value with its source and certainty."""
    if context.fixture():
        notice = "This build runs test content. Its numbers have no research behind them and are not a real plan."
        return "Where the numbers come from", [notice], [], []
    asked = [item for item, words in EVIDENCE_ITEMS if context.words & words] or list(DEFAULT_EVIDENCE)
    profile = context.state["profile"]
    goal, experience = profile["goal"], profile["experience"]
    lines: list[str] = []
    keys: list[str] = []
    for item in asked:
        line, item_keys = _evidence_line(context, item, goal, experience)
        if line:
            lines.append(line)
            keys.extend(key for key in item_keys if key not in keys)
    return "Where the numbers come from", lines, [], keys


def _evidence_line(context: ChatContext, item: str, goal: str, experience: str) -> tuple[str, list[str]]:
    """One evidence answer line: the athlete's value and what it rests on."""
    slot_values = ("template", "slotByGoal", goal)
    if item == "reps":
        lower = context.citations.cited(*slot_values, "lowerReps")
        upper = context.citations.cited(*slot_values, "upperReps")
        if lower is None or upper is None:
            return "", []
        text, keys = context.citations.basis(lower)
        return f"Reps, {lower['value']}–{upper['value']} per set: {text}", keys
    if item == "sets":
        return _sets_line(context, goal, experience)
    if item == "rest":
        rest = context.citations.cited(*slot_values, "restSeconds")
        if rest is None:
            return "", []
        text, keys = context.citations.basis(rest)
        return f"Rest, {rest['value']} seconds between sets: {text}", keys
    if item == "progression":
        slot = next(iter(context.plan_slots()), None)
        if slot is None:
            return "", []
        return progression_rule(context, slot)
    maximum = context.citations.cited("planner", "weekly", "maxSessionsPerWeek")
    if maximum is None:
        return "", []
    text, keys = context.citations.basis(maximum)
    return f"Days, at most {maximum['value']} sessions a week: {text}", keys


def _sets_line(context: ChatContext, goal: str, experience: str) -> tuple[str, list[str]]:
    """The weekly set target per muscle (weekly planner), or the sets per exercise (template)."""
    targets = context.citations.cited("planner", "targets")
    if targets is not None:
        target = (targets["value"].get(goal) or {}).get(experience)
        if target is not None:
            text, keys = context.citations.basis(targets)
            floor = context.citations.cited("planner", "weekly", "weeklySetsFloor")
            line = f"Sets, {target} a week for each major muscle: {text}"
            if floor is not None:
                floor_text, floor_keys = context.citations.brief_basis(floor)
                line += f" The floor of {floor['value']} sets comes from {floor_text}."
                keys = keys + [key for key in floor_keys if key not in keys]
            return line, keys
    sets = context.citations.cited("template", "slotByGoal", goal, "workingSets")
    if sets is None:
        return "", []
    text, keys = context.citations.basis(sets)
    return f"Sets, {sets['value']} per exercise: {text}", keys


def diet(context: ChatContext) -> Answer:
    """Today's targets and what is left, from the Diet tab's own view."""
    view = diet_view(context.state, context.now, context.day_start)
    actions = [action("openDiet", "Open Diet")]
    if view["status"] != "ready":
        return "Today's food", [view["message"]], actions, []
    targets, remaining = view["targets"], view["remaining"]
    lines = [
        f"Today's targets: {targets['energyKcal']:.0f} kcal and {targets['proteinG']:.0f} g protein.",
        f"Left today from the meals you logged: {remaining['calories']:.0f} kcal, "
        f"{remaining['protein']:.0f} g protein, {remaining['carbs']:.0f} g carbs and {remaining['fat']:.0f} g fat.",
    ]
    ideas = [food["name"] for food in view["suggestions"][:3]]
    if ideas:
        lines.append("Foods that fit what's left: " + join_words(ideas) + ".")
    return "Today's food", lines, actions, []


def other() -> Answer:
    """What chat can answer, as questions to tap."""
    lines = [
        "I answer from your own records and the app's cited research, and anything I suggest is a "
        "proposal you accept. Try one of these:"
    ]
    actions = [ask(message, {"topic": topic}) for message, topic in STARTERS]
    return "Something else", lines, actions, []
