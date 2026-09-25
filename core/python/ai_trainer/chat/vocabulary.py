"""Words that decide parts of a chat answer without the model (singular stems from ``spoken_words``)."""

from __future__ import annotations

from ..wording import WEEKDAY_NAMES

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
