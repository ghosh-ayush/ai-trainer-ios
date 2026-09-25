"""Chat answers about training: progress, the next session, the week, time and plan changes.

Each answer comes from logged sets and from the decision the app would make now (the same
``decide`` call a proposal uses); plan changes are offered as proposals, never made here.
"""

from __future__ import annotations

from ..athlete_state import active_status, estimated_minutes
from ..progress import session_summary
from ..queries import comparable_sessions, working_logs
from ..rings import muscle_rings
from ..rules.eligibility import decide
from ..wording import WEEKDAY_NAMES, WEEKDAY_SHORT, join_words
from .actions import action, ask_exercise
from .context import JSON, Answer, ChatContext
from .vocabulary import DAY_WORDS, HARDER_WORDS, LIGHTER_WORDS, STATUS_LABELS

RECENT_SESSIONS = 2
MAX_EXERCISE_BUTTONS = 6

SETUP_REASONS = frozenset({"BASELINE_REQUIRED", "EQUIPMENT_STEP_UNKNOWN", "HISTORY_STALE", "LOAD_CONTEXT_CHANGED"})
BLOCKED_REASONS = frozenset({"REPORTED_PAIN", "EXERCISE_EXCLUDED"})


def exercise_progress(context: ChatContext, exercise_id: str | None, ambiguous: list[str]) -> Answer:
    """How one exercise is going and why its load or reps are (not) going up."""
    if exercise_id is None:
        return _training_overview(context, ambiguous)
    name = context.name(exercise_id)
    slot, plan = context.slot_for(exercise_id)
    if slot is None or plan is None:
        return f"How {name} is going", [f"{name} is not in your plan."], [], []
    lines = [_last_time(context, slot, name)]
    actions: list[JSON] = []
    if plan is context.plan and context.session is None:
        decision = decide(context.state, {"kind": "progression", "slotID": slot["id"]}, context.library, context.now)
        lines.append(decision["explanation"])
        if decision["reason"] == "EFFORT_UNKNOWN":
            lines.append("Log reps in reserve with each set, so the app knows how hard it was.")
        actions = _progress_actions(decision, slot, name)
    elif context.session is not None:
        lines.append("You are in a workout, so the app decides on the next change after it ends.")
    else:
        lines.append(f"It is not in your next session, so the app decides on it when {plan['name']} comes up.")
    rule, keys = progression_rule(context, slot)
    lines.append(rule)
    return f"How {name} is going", lines, actions, keys


def _training_overview(context: ChatContext, ambiguous: list[str]) -> Answer:
    """Each exercise of the current or next session: the last result and the app's decision."""
    if ambiguous:
        actions = [ask_exercise(context.names[key]) for key in ambiguous[:MAX_EXERCISE_BUTTONS]]
        return "Which exercise?", ["Which exercise do you mean?"], actions, []
    rows: list[tuple[str, str, str]] = []  # name, last time, the app's decision
    for slot in context.plan_slots():
        name = context.name(slot["exerciseID"])
        explanation = ""
        if context.session is None:
            decision = decide(
                context.state, {"kind": "progression", "slotID": slot["id"]}, context.library, context.now
            )
            explanation = decision["explanation"]
        rows.append((name, _last_time(context, slot, name, brief=True), explanation))
    shared = {explanation for _, _, explanation in rows}
    if len(rows) > 1 and len(shared) == 1:
        lines = [f"{name} — {last}" for name, last, _ in rows]
        if rows[0][2]:
            lines.append(f"For every exercise: {rows[0][2]}")
    else:
        lines = [f"{name} — {last} {explanation}".rstrip() for name, last, explanation in rows]
    actions = [ask_exercise(context.name(slot["exerciseID"])) for slot in context.plan_slots()[:MAX_EXERCISE_BUTTONS]]
    return "How your training is going", lines, actions, []


def next_session(context: ChatContext) -> Answer:
    """The workout in progress, or the next one, exercise by exercise."""
    lines: list[str] = []
    session = context.session
    if session is not None:
        logged = sum(1 for log in session["logs"] if log["kind"] == "working")
        total = sum(slot["workingSets"] for slot in session["plan"]["slots"])
        lines.append(f"You are in {session['plan']['name']}: {logged} of {total} working sets logged.")
        return "Your workout", lines, [action("openToday", "Back to the workout")], []
    plan = context.plan
    assert plan is not None
    when = f" on {WEEKDAY_NAMES[plan['weekday']]}" if plan.get("weekday") is not None else ""
    adjusted = " (adjusted for this session)" if plan["modified"] else ""
    lines.append(f"Next: {plan['name']}{when}, about {estimated_minutes(plan)} minutes{adjusted}.")
    for slot in plan["slots"]:
        lines.append(_prescription(context, slot))
    status = active_status(context.state, context.now)
    if status is not None:
        lines.append(f"You are marked {STATUS_LABELS[status['kind']]}, so the app's own suggestions are paused.")
    return "Your next workout", lines, [action("openToday", "Open Today")], []


def week(context: ChatContext) -> Answer:
    """The accepted week and this week's logged sets per major muscle."""
    plans = program_plans(context)
    weekly = sorted((plan for plan in plans if plan.get("weekday") is not None), key=lambda plan: plan["weekday"])
    lines: list[str] = []
    if weekly:
        days = [
            f"{WEEKDAY_SHORT[plan['weekday']]} {plan['name']} (about {estimated_minutes(plan)} min)" for plan in weekly
        ]
        lines.append("Your week: " + ", ".join(days) + ".")
    else:
        count = f"{len(plans)} session{'s' if len(plans) != 1 else ''}"
        lines.append(f"Your plan rotates {count}: " + ", ".join(plan["name"] for plan in plans) + ".")
    rings = muscle_rings(context.state, context.library, context.now, context.day_start, context.utc_offset)
    if rings is not None:
        counts = [f"{ring['muscle']} {_count(ring['done'])} of {_count(ring['target'])}" for ring in rings["muscles"]]
        lines.append("Sets logged this week against the weekly target: " + ", ".join(counts) + ".")
    actions = [action("openToday", "Open Today")]
    if weekly and "planner" in context.library:
        actions.insert(0, action("requestReplan", "See if another week fits better"))
    return "Your week", lines, actions, []


def less_time(context: ChatContext, minutes: int | None) -> Answer:
    """What a shorter session would drop, from the same decision the Less time button asks for."""
    if minutes is None:
        lines = [
            "How many minutes do you have? A shorter session drops optional exercises for this session "
            "only; warm-up and rest stay as they are."
        ]
        return "Less time today", lines, [action("openLessTime", "Choose minutes")], []
    decision = decide(context.state, {"kind": "shorten", "minutes": minutes}, context.library, context.now)
    lines = [f"With {minutes} minutes: {decision['explanation']}"]
    actions: list[JSON] = []
    if decision["outcome"] == "proposeChange" and context.plan is not None:
        kept = {slot["id"] for slot in decision["after"]["slots"]}
        dropped = [context.name(slot["exerciseID"]) for slot in context.plan["slots"] if slot["id"] not in kept]
        if dropped:
            lines.append("It drops " + join_words(dropped) + ".")
        actions.append(action("requestShorten", f"Preview the {minutes}-minute session", minutes=minutes))
    elif decision["reason"] == "REQUIRED_WORK_DOES_NOT_FIT":
        actions.append(action("openMoveDay", "Move the session instead"))
    actions.append(action("openLessTime", "Choose other minutes"))
    return f"Less time: {minutes} minutes", lines, actions, []


def move_or_skip(context: ChatContext) -> Answer:
    """What moving and skipping do, with both controls."""
    if context.session is not None:
        return (
            "Moving or skipping",
            ["Finish or end the workout in progress first."],
            [action("openToday", "Open Today")],
            [],
        )
    lines = [
        "Moving puts the next session on another day without changing the order or adding missed work.",
        "Skipping records it as skipped, and the weekly review counts it as missed.",
        "If you'll be away for a few days, mark a break instead: those days don't count as missed.",
    ]
    actions = [
        action("openMoveDay", "Move the session"),
        action("confirmSkip", "Skip this session"),
        action("openStatus", "Mark a break"),
    ]
    return "Moving or skipping a session", lines, actions, []


def change_plan(context: ChatContext, exercise_id: str | None) -> Answer:
    """What can change and how, without inventing a change the content has no rule for."""
    lines = ["The plan changes only through cited rules, as proposals you accept."]
    actions: list[JSON] = []
    keys: list[str] = []
    in_session = {slot["id"]: slot for slot in context.plan_slots() if context.session is None}
    slot = next((slot for slot in in_session.values() if slot["exerciseID"] == exercise_id), None)
    if slot is not None:
        actions.append(action("openSwap", f"Swap {context.name(slot['exerciseID'])} for today", slotID=slot["id"]))
    if context.words & HARDER_WORDS:
        rule_slot = slot or next(iter(in_session.values()), None)
        if rule_slot is not None:
            rule, keys = progression_rule(context, rule_slot)
            lines.append(f"It gets harder as your logged sets qualify. {rule}")
    if context.words & LIGHTER_WORDS:
        lines.append(no_lighter_rule())
    if context.words & DAY_WORDS:
        lines.append(
            "You can change your free days and minutes at any time; the app proposes a week that fits, "
            "and loads you confirmed carry over. Changing equipment isn't in the app yet."
        )
        actions.append(action("openChangeDays", "Change my free days"))
    actions.append(action("openLessTime", "Shorter session today"))
    if "planner" in context.library and any(plan.get("weekday") is not None for plan in program_plans(context)):
        actions.append(action("requestReplan", "See if another week fits better"))
    actions.append(action("openToday", "Swap an exercise on Today"))
    return "Changing the plan", lines, actions, keys


def _last_time(context: ChatContext, slot: JSON, name: str, brief: bool = False) -> str:
    """ "Last time: Mon 21 Sep, 20 kg × 10 / 10 / 9 · RIR 2; …" from the latest comparable sessions.

    ``brief`` is for a list that already names the exercise: "nothing logged yet." or
    "last Mon 21 Sep, 20 kg × 10 / 10 / 9 · RIR 2."
    """
    history = [
        session for session in comparable_sessions(context.state, slot, context.now) if working_logs(session, slot)
    ]
    if not history:
        return "nothing logged yet." if brief else f"No {name} sets are logged yet."
    if brief:
        return f"last {context.day(history[0]['startedAt'])}, {session_summary(history[0], slot)}."
    recent = [
        f"{context.day(session['startedAt'])}, {session_summary(session, slot)}"
        for session in history[:RECENT_SESSIONS]
    ]
    return "Last time: " + "; ".join(recent) + "."


def progression_rule(context: ChatContext, slot: JSON) -> tuple[str, list[str]]:
    """The load-and-rep rule in words, with what each of its numbers rests on."""
    policy = context.library["policy"]
    percent = round(policy["maximumIncreaseFraction"] * 100)
    rule = (
        f"How it moves up: one more target rep at a time until every working set reaches {slot['upperReps']} reps "
        f"with at least {policy['minimumRIR']} reps in reserve in {policy['requiredExposures']} sessions in a row, "
        f"then the next weight you have, at most {percent}% heavier."
    )
    if context.fixture():
        return rule + " These are test numbers with no research behind them.", []
    parts: list[str] = []
    keys: list[str] = []
    for label, field in (
        ("sessions in a row", "requiredExposures"),
        ("reps in reserve", "minimumRIR"),
        ("largest step", "maximumIncreaseFraction"),
    ):
        text, item_keys = context.citations.brief_basis(context.citations.cited("policy", field))
        parts.append(f"{label}: {text}")
        keys.extend(key for key in item_keys if key not in keys)
    return rule + " Based on " + "; ".join(parts) + ".", keys


def _prescription(context: ChatContext, slot: JSON) -> str:
    """ "Goblet squat: 4 × 8 / 8 / 8 / 8 reps at 20 kg" or "…, load not set (optional)"."""
    targets = " / ".join(str(target) for target in slot["targets"])
    load = slot.get("load")
    weight = f" at {load:g} {slot['equipment']['unit']}" if load is not None else ", load not set"
    optional = " (optional)" if slot["optional"] else ""
    return f"{context.name(slot['exerciseID'])}: {slot['workingSets']} × {targets} reps{weight}{optional}"


def _progress_actions(decision: JSON, slot: JSON, name: str) -> list[JSON]:
    """The control that moves this exercise forward, if any."""
    if decision["outcome"] == "proposeChange":
        return [action("requestProgression", f"See the proposal for {name}", slotID=slot["id"])]
    if decision["reason"] in SETUP_REASONS:
        return [action("openLoad", f"Set the {name} load", slotID=slot["id"])]
    if decision["reason"] in BLOCKED_REASONS:
        return [action("openSwap", f"Swap {name} for today", slotID=slot["id"])]
    return []


def program_plans(context: ChatContext) -> list[JSON]:
    """Every plan of the accepted program, or none before a plan is accepted."""
    return list((context.state.get("program") or {}).get("plans", []))


def no_lighter_rule() -> str:
    """Why chat offers no lighter week: the content has no cited rule for one."""
    return (
        "There is no cited rule for a lighter week, so the app won't make one up. "
        "A shorter session drops optional work for one session."
    )


def _count(value: float) -> str:
    return f"{value:g}"
