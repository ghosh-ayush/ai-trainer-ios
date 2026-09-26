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

Layout: ``context`` grounds the draft and holds what an answer reads; ``training``, ``wellbeing``
and ``info`` write the answers by topic; ``actions`` builds the buttons; ``vocabulary`` holds the
words that decide parts of an answer without the model. Citations come from ``..citations``.
"""

from __future__ import annotations

from ..athlete_state import active_session, next_plan
from ..errors import require
from ..spoken_sets import MAX_TEXT_LENGTH
from . import info, training, wellbeing
from .context import DAYS_RANGE, JSON, MINUTES_RANGE, ChatContext
from .vocabulary import PAIN_WORDS

__all__ = ["chat_reply"]


def chat_reply(
    state: JSON,
    text: str,
    draft: JSON,
    library: JSON,
    bundle: tuple[JSON, JSON],
    now: float,
    day_start: float | None = None,
    utc_offset: int | None = None,
    earlier: str | None = None,
) -> JSON:
    """Answer one chat message from the athlete's records and the cited content. Read-only.

    ``draft`` is what the on-device model read from ``text``; ``bundle`` is the active content
    bundle's raw ``(manifest, content)``, citations included; ``earlier`` is the athlete's previous
    message, so a follow-up keeps its exercise. Returns a ``ChatReply``.
    """
    words = text.strip()
    require(0 < len(words) <= MAX_TEXT_LENGTH, "invalid", "Ask in up to 500 characters.")
    context = ChatContext(state, words, library, bundle, now, day_start, utc_offset, earlier)
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
        answer = training.exercise_progress(context, exercise_id, ambiguous)
    elif topic == "nextSession":
        answer = training.next_session(context)
    elif topic == "week":
        answer = training.week(context)
    elif topic == "lessTime":
        answer = training.less_time(context, minutes)
    elif topic == "moveOrSkip":
        answer = training.move_or_skip(context)
    elif topic == "pain":
        answer = wellbeing.pain(context, exercise_id)
    elif topic == "away":
        answer = wellbeing.away(context, days)
    elif topic == "changePlan":
        answer = training.change_plan(context, exercise_id)
    elif topic == "evidence":
        answer = info.evidence(context)
    elif topic == "diet":
        answer = info.diet(context)
    else:
        answer = info.other()
    reading, lines, actions, source_keys = answer
    return _reply(context, topic, reading, lines, actions, source_keys, ignored)


def _reply(
    context: ChatContext,
    topic: str,
    reading: str,
    lines: list[str],
    actions: list[JSON],
    source_keys: list[str],
    ignored: list[str],
) -> JSON:
    """The ``ChatReply`` record, with the cited sources looked up in the active bundle."""
    return {
        "topic": topic,
        "reading": reading,
        "lines": lines,
        "actions": actions,
        "sources": context.citations.entries(source_keys),
        "ignored": ignored,
    }
