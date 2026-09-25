"""Chat with the app (ADR-023): the on-device model reads a message, the core answers it.

The athlete types a message ("why is my squat not going up?", "my knee hurts"). Apple's
on-device language model fills a ``ChatDraft``: one topic from a fixed list and any exercise,
minutes or days it saw. The model only reads. This module decides what the draft may say and
writes the whole answer, the way ``read_set`` treats a set described in words (ADR-015):

- A number counts only if it appears in the athlete's words, and an exercise only if the athlete
  said a word of its name. Anything else the model supplied is dropped and named in ``ignored``.
- Pain words always get the pain answer, whatever topic the model chose.
- Every sentence is built here from the athlete's records, the decision the app would make now
  (the same ``decide`` call a proposal uses) and the active bundle's cited values. The model
  writes none of it, so it cannot invent a number, a rule or a study.
- An answer changes nothing. It offers actions; each needs the athlete's tap, and a plan change
  it starts is still a Recommendation the athlete accepts (rule 3).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from .athlete_state import active_session, active_status, estimated_minutes, next_plan
from .content import exercises_by_id
from .diet_view import diet_view
from .errors import require
from .progress import session_summary
from .queries import comparable_sessions, working_logs
from .rings import muscle_rings
from .rules.eligibility import decide
from .spoken_sets import MAX_TEXT_LENGTH, NUMBER_WORDS, spoken_numbers, spoken_words

JSON = dict[str, Any]

DAY = 86400.0
MINUTE = 60
REFERENCE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
WEEKDAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
SHORTEST_NAME_WORD = 3
RECENT_SESSIONS = 2
MAX_EXERCISE_BUTTONS = 6
MINUTES_RANGE = (5, 600)
DAYS_RANGE = (1, 365)

# Singular word stems (``spoken_words``) that decide parts of an answer without the model.
PAIN_WORDS = frozenset(
    {
        "pain",
        "painful",
        "hurt",
        "hurting",
        "ache",
        "aching",
        "sore",
        "injury",
        "injured",
        "tweak",
        "tweaked",
        "strain",
        "strained",
        "sprain",
        "sprained",
    }
)
STATUS_WORDS: dict[str, frozenset[str]] = {
    "sick": frozenset({"sick", "ill", "unwell", "flu", "cold", "fever", "covid", "virus", "infection"}),
    "injured": frozenset({"injury", "injured"}),
    "onBreak": frozenset({"holiday", "vacation", "travel", "traveling", "travelling", "trip", "away", "break", "busy"}),
}
BACK_WORDS = frozenset({"back", "returned"})
LIGHTER_WORDS = frozenset({"lighter", "easier", "lighten", "deload"})
HARDER_WORDS = frozenset({"harder", "heavier", "tougher", "increase"})
DAY_WORDS = frozenset({"day", "weekend", "weekday", *(name.casefold() for name in WEEKDAY_NAMES)})

STATUS_LABELS = {"onBreak": "on a break", "sick": "sick", "injured": "injured"}

# Evidence items a question can ask about, in answer order, and the words that pick each one.
EVIDENCE_ITEMS: tuple[tuple[str, frozenset[str]], ...] = (
    ("reps", frozenset({"rep", "repetition", "range"})),
    ("sets", frozenset({"set", "volume"})),
    ("rest", frozenset({"rest", "second", "minute", "pause"})),
    ("progression", frozenset({"weight", "load", "heavier", "progress", "progression", "increase", "kg", "lb"})),
    ("days", frozenset({"day", "week", "often", "frequency"})),
)
DEFAULT_EVIDENCE = ("reps", "sets", "rest", "progression")

SETUP_REASONS = frozenset({"BASELINE_REQUIRED", "EQUIPMENT_STEP_UNKNOWN", "HISTORY_STALE", "LOAD_CONTEXT_CHANGED"})
BLOCKED_REASONS = frozenset({"REPORTED_PAIN", "EXERCISE_EXCLUDED"})

# Source keys as the bundles write them (ACSM26, SCHOENFELD17V): capitals, then two digits.
SOURCE_KEY = re.compile(r"\b[A-Z][A-Z]+\d{2}[A-Z]*\b")

# The questions offered when the app cannot tell what was asked, and as starters in the host.
STARTERS: tuple[tuple[str, str], ...] = (
    ("How is my training going?", "exerciseProgress"),
    ("What's my next workout?", "nextSession"),
    ("What's my week?", "week"),
    ("I have less time today", "lessTime"),
    ("Something hurts", "pain"),
    ("I'm sick or away", "away"),
    ("Where do the numbers come from?", "evidence"),
)


def chat_reply(
    state: JSON,
    text: str,
    draft: JSON,
    library: JSON,
    bundle: tuple[JSON, JSON],
    now: float,
    day_start: float | None = None,
    utc_offset: int | None = None,
) -> JSON:
    """Answer one chat message from the athlete's records and the cited content. Read-only.

    ``draft`` is what the on-device model read from ``text``; ``bundle`` is the active content
    bundle's raw ``(manifest, content)``, citations included. Returns a ``ChatReply``.
    """
    words = text.strip()
    require(0 < len(words) <= MAX_TEXT_LENGTH, "invalid", "Ask in up to 500 characters.")
    context = _Context(state, words, library, bundle, now, day_start, utc_offset)
    ignored: list[str] = []
    exercise_id, ambiguous = context.grounded_exercise(draft.get("exercise"), ignored)
    minutes = context.grounded_number(draft.get("minutes"), context.minute_values(), MINUTES_RANGE, "minutes", ignored)
    days = context.grounded_number(draft.get("days"), context.day_values(), DAYS_RANGE, "days", ignored)

    topic = draft["topic"]
    if context.words & PAIN_WORDS:
        topic = "pain"  # safety first: pain words always get the pain answer
    if next_plan(state) is None and active_session(state) is None:
        return _reply(context, topic, "Your plan", ["Accept a plan first; then I can answer from it."], [], [], ignored)

    if topic == "exerciseProgress":
        answer = _exercise_progress(context, exercise_id, ambiguous)
    elif topic == "nextSession":
        answer = _next_session(context)
    elif topic == "week":
        answer = _week(context)
    elif topic == "lessTime":
        answer = _less_time(context, minutes)
    elif topic == "moveOrSkip":
        answer = _move_or_skip(context)
    elif topic == "pain":
        answer = _pain(context, exercise_id)
    elif topic == "away":
        answer = _away(context, days)
    elif topic == "changePlan":
        answer = _change_plan(context, exercise_id)
    elif topic == "evidence":
        answer = _evidence(context)
    elif topic == "diet":
        answer = _diet(context)
    else:
        answer = _other()
    reading, lines, actions, source_keys = answer
    return _reply(context, topic, reading, lines, actions, source_keys, ignored)


# --- context --------------------------------------------------------------------------------


class _Context:
    """Everything one answer reads, gathered once."""

    def __init__(
        self,
        state: JSON,
        text: str,
        library: JSON,
        bundle: tuple[JSON, JSON],
        now: float,
        day_start: float | None,
        utc_offset: int | None,
    ) -> None:
        self.state = state
        self.library = library
        self.manifest, self.raw = bundle
        self.now = now
        self.day_start = day_start
        self.utc_offset = utc_offset
        self.text = text.casefold()
        self.words = spoken_words(text)
        self.numbers = spoken_numbers(text)
        self.exercises = exercises_by_id(library)
        self.session = active_session(state)
        self.plan = self.session["plan"] if self.session is not None else next_plan(state)
        self.names = self._candidate_names()

    def name(self, exercise_id: str) -> str:
        """The exercise's library name, or its id when the library no longer has it."""
        exercise = self.exercises.get(exercise_id)
        return exercise["name"] if exercise else exercise_id

    def day(self, seconds: float) -> str:
        """ "Mon 21 Sep" in the athlete's time zone (UTC when the host sent no offset)."""
        moment = REFERENCE_EPOCH + dt.timedelta(seconds=seconds + (self.utc_offset or 0))
        return f"{WEEKDAY_SHORT[moment.weekday()]} {moment.day} {MONTHS[moment.month - 1]}"

    def fixture(self) -> bool:
        """Whether this build runs test content, which rests on no research."""
        return bool(self.library["policy"]["review"] == "fixture")

    def plan_slots(self) -> list[JSON]:
        """The slots of the session in progress, or of the next one."""
        return list(self.plan["slots"]) if self.plan else []

    def slot_for(self, exercise_id: str) -> tuple[JSON | None, JSON | None]:
        """``(slot, plan)`` for the exercise: the current or next session first, then any plan."""
        plans = ([self.plan] if self.plan else []) + list((self.state.get("program") or {}).get("plans", []))
        for plan in plans:
            for slot in plan["slots"]:
                if slot["exerciseID"] == exercise_id:
                    return slot, plan
        return None, None

    def grounded_exercise(self, named: str | None, ignored: list[str]) -> tuple[str | None, list[str]]:
        """The exercise the athlete named, and the candidates when that is ambiguous.

        An exercise is *heard* when the athlete said a word only its name contains, and
        *mentioned* when they said any word of its name. The model's pick wins among the
        mentioned exercises; otherwise one heard exercise wins alone. The model's pick is ignored
        when the athlete said no word of it.
        """
        heard = [key for key in self.names if self._distinctive(key) & self.words]
        mentioned = [key for key in self.names if self._name_words(self.names[key]) & self.words]
        if named is not None:
            picked = next((key for key in self.names if _fold(self.names[key]) == _fold(named)), None)
            if picked is not None and picked in mentioned and (picked in heard or len(mentioned) == 1):
                return picked, []
            if picked is None or picked not in mentioned:
                ignored.append("exercise")
        if len(heard) == 1:
            return heard[0], []
        if len(mentioned) == 1:
            return mentioned[0], []
        return None, heard or mentioned

    def grounded_number(
        self, value: int | None, heard: set[float], bounds: tuple[int, int], field: str, ignored: list[str]
    ) -> int | None:
        """``value`` when the athlete said it (and it is in ``bounds``), otherwise ``None``."""
        if value is None:
            return None
        if float(value) not in heard or not bounds[0] <= value <= bounds[1]:
            ignored.append(field)
            return None
        return int(value)

    def minute_values(self) -> set[float]:
        """Minutes the words can mean: numbers said, "2 hours", "an hour", "half an hour"."""
        values = set(self.numbers)
        text = self.text
        if re.search(r"\b(?:an|a|one) hour and a half\b", text):
            values.add(MINUTE * 1.5)
            text = re.sub(r"\b(?:an|a|one) hour and a half\b", " ", text)
        if re.search(r"\bhalf (?:an |a )?hour\b", text):
            values.add(MINUTE / 2)
            text = re.sub(r"\bhalf (?:an |a )?hour\b", " ", text)
        values |= {count * MINUTE for count in _counted(text, "hour")}
        return values

    def day_values(self) -> set[float]:
        """Days the words can mean: numbers said, "2 weeks", "a week", "a fortnight"."""
        values = set(self.numbers)
        values |= {count * 7 for count in _counted(self.text, "week")}
        if re.search(r"\bfortnight\b", self.text):
            values.add(14.0)
        return values

    def citation(self, *path: str) -> JSON | None:
        """The cited value at ``path`` in the raw bundle, or ``None`` when it is absent or uncited."""
        node: Any = self.raw
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        if isinstance(node, dict) and "value" in node and "source" in node:
            return node
        return None

    def basis(self, node: JSON | None) -> tuple[str, list[str]]:
        """How a cited value is backed, as a sentence, and the source keys it names."""
        if node is None:
            return "This content cites nothing for it.", []
        if node["source"] == "owner":
            rationale = str(node.get("rationale", ""))
            return f"No study gives this exact number, so it is the app's own rule. {rationale}", self.keys_in(
                rationale
            )
        sentence = f"From {self.short_citation(node['source'])}"
        if node.get("certainty"):
            sentence += f" ({node['certainty']} certainty)"
        sentence += "."
        note = str(node.get("note", ""))
        if note:
            sentence += f" {note}"
        return sentence, [node["source"], *(key for key in self.keys_in(note) if key != node["source"])]

    def brief_basis(self, node: JSON | None) -> tuple[str, list[str]]:
        """``basis`` in a few words: the source and certainty, or "the app's own rule"."""
        if node is None:
            return "no citation", []
        if node["source"] == "owner":
            return "the app's own rule, built from cited research", self.keys_in(str(node.get("rationale", "")))
        certainty = f", {node['certainty']} certainty" if node.get("certainty") else ""
        return f"{self.short_citation(node['source'])}{certainty}", [node["source"]]

    def keys_in(self, text: str) -> list[str]:
        """The bundle's source keys named in ``text``, once each, in order."""
        found: list[str] = []
        for key in SOURCE_KEY.findall(text):
            if key in self.manifest.get("sources", {}) and key not in found:
                found.append(key)
        return found

    def short_citation(self, key: str) -> str:
        """ "Baz-Valle et al. 2022" or "American College of Sports Medicine 2009" from the citation."""
        source = self.manifest.get("sources", {}).get(key)
        if source is None:
            return key
        citation = str(source["citation"])
        authors = citation.split(". ")[0]
        first = authors.split(",")[0].strip()
        if "," in authors:
            first = first.split(" ")[0] + " et al."
        year = re.search(r"\b(?:19|20)\d{2}\b", citation)
        return f"{first} {year.group(0)}" if year else first

    def _candidate_names(self) -> dict[str, str]:
        """Exercise id -> name for every exercise in the current or next session and the program."""
        plans = ([self.plan] if self.plan else []) + list((self.state.get("program") or {}).get("plans", []))
        names: dict[str, str] = {}
        for plan in plans:
            for slot in plan["slots"]:
                names.setdefault(slot["exerciseID"], self.name(slot["exerciseID"]))
        return names

    def _distinctive(self, exercise_id: str) -> set[str]:
        own = self._name_words(self.names[exercise_id])
        for other, name in self.names.items():
            if other != exercise_id:
                own -= self._name_words(name)
        return own

    @staticmethod
    def _name_words(name: str) -> set[str]:
        return {word for word in spoken_words(name) if len(word) >= SHORTEST_NAME_WORD and word not in NUMBER_WORDS}


Answer = tuple[str, list[str], list[JSON], list[str]]  # reading, lines, actions, source keys


# --- topics ---------------------------------------------------------------------------------


def _exercise_progress(context: _Context, exercise_id: str | None, ambiguous: list[str]) -> Answer:
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
    rule, keys = _progression_rule(context, slot)
    lines.append(rule)
    return f"How {name} is going", lines, actions, keys


def _training_overview(context: _Context, ambiguous: list[str]) -> Answer:
    """Each exercise of the current or next session: the last result and the app's decision."""
    if ambiguous:
        actions = [_ask_exercise(context.names[key]) for key in ambiguous[:MAX_EXERCISE_BUTTONS]]
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
    actions = [_ask_exercise(context.name(slot["exerciseID"])) for slot in context.plan_slots()[:MAX_EXERCISE_BUTTONS]]
    return "How your training is going", lines, actions, []


def _next_session(context: _Context) -> Answer:
    """The workout in progress, or the next one, exercise by exercise."""
    lines: list[str] = []
    session = context.session
    if session is not None:
        logged = sum(1 for log in session["logs"] if log["kind"] == "working")
        total = sum(slot["workingSets"] for slot in session["plan"]["slots"])
        lines.append(f"You are in {session['plan']['name']}: {logged} of {total} working sets logged.")
        return "Your workout", lines, [_action("openToday", "Back to the workout")], []
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
    return "Your next workout", lines, [_action("openToday", "Open Today")], []


def _week(context: _Context) -> Answer:
    """The accepted week and this week's logged sets per major muscle."""
    plans = _program_plans(context)
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
    actions = [_action("openToday", "Open Today")]
    if weekly and "planner" in context.library:
        actions.insert(0, _action("requestReplan", "See if another week fits better"))
    return "Your week", lines, actions, []


def _less_time(context: _Context, minutes: int | None) -> Answer:
    """What a shorter session would drop, from the same decision the Less time button asks for."""
    if minutes is None:
        lines = [
            "How many minutes do you have? A shorter session drops optional exercises for this session "
            "only; warm-up and rest stay as they are."
        ]
        return "Less time today", lines, [_action("openLessTime", "Choose minutes")], []
    decision = decide(context.state, {"kind": "shorten", "minutes": minutes}, context.library, context.now)
    lines = [f"With {minutes} minutes: {decision['explanation']}"]
    actions: list[JSON] = []
    if decision["outcome"] == "proposeChange" and context.plan is not None:
        kept = {slot["id"] for slot in decision["after"]["slots"]}
        dropped = [context.name(slot["exerciseID"]) for slot in context.plan["slots"] if slot["id"] not in kept]
        if dropped:
            lines.append("It drops " + _join(dropped) + ".")
        actions.append(_action("requestShorten", f"Preview the {minutes}-minute session", minutes=minutes))
    elif decision["reason"] == "REQUIRED_WORK_DOES_NOT_FIT":
        actions.append(_action("openMoveDay", "Move the session instead"))
    actions.append(_action("openLessTime", "Choose other minutes"))
    return f"Less time: {minutes} minutes", lines, actions, []


def _move_or_skip(context: _Context) -> Answer:
    """What moving and skipping do, with both controls."""
    if context.session is not None:
        return (
            "Moving or skipping",
            ["Finish or end the workout in progress first."],
            [_action("openToday", "Open Today")],
            [],
        )
    lines = [
        "Moving puts the next session on another day without changing the order or adding missed work.",
        "Skipping records it as skipped, and the weekly review counts it as missed.",
        "If you'll be away for a few days, mark a break instead: those days don't count as missed.",
    ]
    actions = [
        _action("openMoveDay", "Move the session"),
        _action("confirmSkip", "Skip this session"),
        _action("openStatus", "Mark a break"),
    ]
    return "Moving or skipping a session", lines, actions, []


def _pain(context: _Context, exercise_id: str | None) -> Answer:
    """Pausing an exercise for pain, marking an injury, and what the app cannot judge."""
    lines = [
        "The app can't assess pain or tell which exercises are safe with it.",
        "Pausing an exercise stops its guidance and pauses a workout in progress. "
        "A different exercise is not assumed safe.",
        "If the pain is severe, getting worse or not settling, get it checked by a clinician.",
    ]
    if context.words & LIGHTER_WORDS:
        lines.append(_no_lighter_rule())
    actions: list[JSON] = []
    in_session = {slot["exerciseID"] for slot in context.plan_slots()}
    reading = "Something hurts"
    if exercise_id is not None and exercise_id in in_session:
        name = context.name(exercise_id)
        reading = f"Something hurts ({name})"
        actions.append(_action("reportPain", f"Pause {name} for pain", exerciseID=exercise_id))
        actions.append(_action("openPain", "Pause a different exercise"))
    else:
        actions.append(_action("openPain", "Choose the exercise to pause"))
    status = active_status(context.state, context.now)
    current = status["kind"] if status is not None else None
    if context.words & STATUS_WORDS["sick"] and current != "sick":
        actions.append(_action("setStatus", "Mark me sick (pauses suggestions)", status="sick"))
    if current != "injured":
        actions.append(_action("setStatus", "Mark me injured (pauses suggestions)", status="injured"))
    return reading, lines, actions, []


def _away(context: _Context, days: int | None) -> Answer:
    """Marking a break, illness or injury, or ending one."""
    status = active_status(context.state, context.now)
    heard_kinds = [kind for kind, words in STATUS_WORDS.items() if context.words & words]
    kind = heard_kinds[0] if len(heard_kinds) == 1 else None  # "sick or away" names no one kind
    back = bool(context.words & BACK_WORDS)
    if status is not None and (back or kind is None):
        label = STATUS_LABELS[status["kind"]]
        until = f" until {context.day(status['endsAt'])}" if status.get("endsAt") else ""
        lines = [f"You are marked {label}{until}. Tap I'm back to resume the app's suggestions."]
        return "Your current status", lines, [_action("endStatus", "I'm back")], []
    if back:
        return "Back from a break", ["You are not marked away, so nothing is paused."], [], []
    explanation = (
        "While you're away the app pauses its own suggestions. Your plan doesn't change, and those days "
        "don't count as missed sessions."
    )
    if kind is None:
        actions = [
            _action("setStatus", f"I'm {STATUS_LABELS[option]}", status=option)
            for option in ("onBreak", "sick", "injured")
        ]
        actions.append(_action("openStatus", "Choose dates"))
        return "Away or unwell", ["Are you on a break, sick or injured?", explanation], actions, []
    label = STATUS_LABELS[kind]
    ends_at = context.now + days * DAY if days is not None else None
    length = f" for {days} day{'s' if days != 1 else ''}" if days is not None else ""
    until = length or " until I'm back"
    title = f"Mark me {label}{until}"
    actions = [_action("setStatus", title, status=kind, endsAt=ends_at), _action("openStatus", "Choose other dates")]
    return f"{label.capitalize()}{length}", [explanation], actions, []


def _change_plan(context: _Context, exercise_id: str | None) -> Answer:
    """What can change and how, without inventing a change the content has no rule for."""
    lines = ["The plan changes only through cited rules, as proposals you accept."]
    actions: list[JSON] = []
    keys: list[str] = []
    in_session = {slot["id"]: slot for slot in context.plan_slots() if context.session is None}
    slot = next((slot for slot in in_session.values() if slot["exerciseID"] == exercise_id), None)
    if slot is not None:
        actions.append(_action("openSwap", f"Swap {context.name(slot['exerciseID'])} for today", slotID=slot["id"]))
    if context.words & HARDER_WORDS:
        rule_slot = slot or next(iter(in_session.values()), None)
        if rule_slot is not None:
            rule, keys = _progression_rule(context, rule_slot)
            lines.append(f"It gets harder as your logged sets qualify. {rule}")
    if context.words & LIGHTER_WORDS:
        lines.append(_no_lighter_rule())
    if context.words & DAY_WORDS:
        lines.append("Changing your free days, minutes or equipment isn't in the app yet.")
    actions.append(_action("openLessTime", "Shorter session today"))
    if "planner" in context.library and any(plan.get("weekday") is not None for plan in _program_plans(context)):
        actions.append(_action("requestReplan", "See if another week fits better"))
    actions.append(_action("openToday", "Swap an exercise on Today"))
    return "Changing the plan", lines, actions, keys


def _evidence(context: _Context) -> Answer:
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


def _diet(context: _Context) -> Answer:
    """Today's targets and what is left, from the Diet tab's own view."""
    view = diet_view(context.state, context.now, context.day_start)
    actions = [_action("openDiet", "Open Diet")]
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
        lines.append("Foods that fit what's left: " + _join(ideas) + ".")
    return "Today's food", lines, actions, []


def _other() -> Answer:
    """What chat can answer, as questions to tap."""
    lines = [
        "I answer from your own records and the app's cited research, and anything I suggest is a "
        "proposal you accept. Try one of these:"
    ]
    actions = [_ask(message, {"topic": topic}) for message, topic in STARTERS]
    return "Something else", lines, actions, []


# --- pieces ---------------------------------------------------------------------------------


def _last_time(context: _Context, slot: JSON, name: str, brief: bool = False) -> str:
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


def _progression_rule(context: _Context, slot: JSON) -> tuple[str, list[str]]:
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
        text, item_keys = context.brief_basis(context.citation("policy", field))
        parts.append(f"{label}: {text}")
        keys.extend(key for key in item_keys if key not in keys)
    return rule + " Based on " + "; ".join(parts) + ".", keys


def _evidence_line(context: _Context, item: str, goal: str, experience: str) -> tuple[str, list[str]]:
    """One evidence answer line: the athlete's value and what it rests on."""
    slot_values = ("template", "slotByGoal", goal)
    if item == "reps":
        lower = context.citation(*slot_values, "lowerReps")
        upper = context.citation(*slot_values, "upperReps")
        if lower is None or upper is None:
            return "", []
        text, keys = context.basis(lower)
        return f"Reps, {lower['value']}–{upper['value']} per set: {text}", keys
    if item == "sets":
        return _sets_line(context, goal, experience)
    if item == "rest":
        rest = context.citation(*slot_values, "restSeconds")
        if rest is None:
            return "", []
        text, keys = context.basis(rest)
        return f"Rest, {rest['value']} seconds between sets: {text}", keys
    if item == "progression":
        slot = next(iter(context.plan_slots()), None)
        if slot is None:
            return "", []
        return _progression_rule(context, slot)
    maximum = context.citation("planner", "weekly", "maxSessionsPerWeek")
    if maximum is None:
        return "", []
    text, keys = context.basis(maximum)
    return f"Days, at most {maximum['value']} sessions a week: {text}", keys


def _sets_line(context: _Context, goal: str, experience: str) -> tuple[str, list[str]]:
    """The weekly set target per muscle (weekly planner), or the sets per exercise (template)."""
    targets = context.citation("planner", "targets")
    if targets is not None:
        target = (targets["value"].get(goal) or {}).get(experience)
        if target is not None:
            text, keys = context.basis(targets)
            floor = context.citation("planner", "weekly", "weeklySetsFloor")
            line = f"Sets, {target} a week for each major muscle: {text}"
            if floor is not None:
                floor_text, floor_keys = context.brief_basis(floor)
                line += f" The floor of {floor['value']} sets comes from {floor_text}."
                keys = keys + [key for key in floor_keys if key not in keys]
            return line, keys
    sets = context.citation("template", "slotByGoal", goal, "workingSets")
    if sets is None:
        return "", []
    text, keys = context.basis(sets)
    return f"Sets, {sets['value']} per exercise: {text}", keys


def _prescription(context: _Context, slot: JSON) -> str:
    """ "Goblet squat: 4 × 8 / 8 / 8 / 8 reps at 20 kg" or "…, load not set (optional)"."""
    targets = " / ".join(str(target) for target in slot["targets"])
    load = slot.get("load")
    weight = f" at {load:g} {slot['equipment']['unit']}" if load is not None else ", load not set"
    optional = " (optional)" if slot["optional"] else ""
    return f"{context.name(slot['exerciseID'])}: {slot['workingSets']} × {targets} reps{weight}{optional}"


def _progress_actions(decision: JSON, slot: JSON, name: str) -> list[JSON]:
    """The control that moves this exercise forward, if any."""
    if decision["outcome"] == "proposeChange":
        return [_action("requestProgression", f"See the proposal for {name}", slotID=slot["id"])]
    if decision["reason"] in SETUP_REASONS:
        return [_action("openLoad", f"Set the {name} load", slotID=slot["id"])]
    if decision["reason"] in BLOCKED_REASONS:
        return [_action("openSwap", f"Swap {name} for today", slotID=slot["id"])]
    return []


def _program_plans(context: _Context) -> list[JSON]:
    return list((context.state.get("program") or {}).get("plans", []))


def _no_lighter_rule() -> str:
    return (
        "There is no cited rule for a lighter week, so the app won't make one up. "
        "A shorter session drops optional work for one session."
    )


def _ask_exercise(name: str) -> JSON:
    return _ask(f"How is {name} going?", {"topic": "exerciseProgress", "exercise": name})


def _ask(message: str, draft: JSON) -> JSON:
    return _action("ask", message, message=message, draft=draft)


def _action(kind: str, title: str, **fields: Any) -> JSON:
    """A ``ChatAction``; fields set to ``None`` are left out."""
    action: JSON = {"kind": kind, "title": title}
    action.update({key: value for key, value in fields.items() if value is not None})
    return action


def _reply(
    context: _Context,
    topic: str,
    reading: str,
    lines: list[str],
    actions: list[JSON],
    source_keys: list[str],
    ignored: list[str],
) -> JSON:
    sources = []
    for key in source_keys:
        source = context.manifest.get("sources", {}).get(key)
        if source is None:
            continue
        entry: JSON = {"key": key, "citation": source["citation"]}
        for identifier in ("doi", "pmid"):
            if source.get(identifier):
                entry[identifier] = str(source[identifier])
        sources.append(entry)
    return {
        "topic": topic,
        "reading": reading,
        "lines": lines,
        "actions": actions,
        "sources": sources,
        "ignored": ignored,
    }


def _counted(text: str, unit: str) -> list[float]:
    """The counts said directly before ``unit``: "2 weeks" -> [2], "a week" -> [1], "three hours" -> [3]."""
    counts: list[float] = []
    for match in re.finditer(rf"\b(\d+(?:\.\d+)?|[a-z]+) {unit}s?\b", text):
        word = match.group(1)
        if word in ("a", "an", "one"):
            counts.append(1.0)
        elif word in NUMBER_WORDS:
            counts.append(float(NUMBER_WORDS[word]))
        elif word[0].isdigit():
            counts.append(float(word))
    return counts


def _count(value: float) -> str:
    return f"{value:g}"


def _join(items: list[str]) -> str:
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _fold(text: str) -> str:
    return text.strip().casefold()
