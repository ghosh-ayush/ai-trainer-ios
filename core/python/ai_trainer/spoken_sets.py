"""Turn a set the athlete described in words into a set preview the athlete confirms.

An on-device language model reads the athlete's words ("bench 80 for 8, one left") and
fills a ``SpokenSet`` draft: which exercise, and which of the spoken numbers are reps, load
and reps in reserve. The model only reads. This module decides what the draft may say
(ADR-015):

- Every number must appear in the athlete's own words. A number the model supplied that the
  athlete never said is dropped and named in ``ignored``: unknown stays unknown (rule 2).
- The exercise must be a slot of the active session, recognised from a word of its name the
  athlete said. With no exercise named, the set belongs to the slot of the next open set; an
  exercise named from outside the session is a question.
- The unit and the set kind come from the athlete's words alone, never from the model.
  A unit other than the slot's is a question, never a silent conversion.
- Reps are required; load and RIR stay absent unless the athlete said them.

The result is a preview. Nothing is saved here: the host sends it as a normal ``saveSet``
only after the athlete taps Save, so it passes the same validation as a set entered by hand.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .athlete_state import active_session, has_working_set
from .commands.workout import MAX_REPS, MAX_RIR
from .content import exercises_by_id
from .errors import require

JSON = dict[str, Any]

MAX_TEXT_LENGTH = 500
SHORTEST_NAME_WORD = 3

_NUMBER_WORD_LIST = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)
NUMBER_WORDS: dict[str, int] = {word: value for value, word in enumerate(_NUMBER_WORD_LIST)}

# Singular word stems that name a unit -> the contract's ``Unit``.
UNIT_WORDS: dict[str, str] = {
    "kg": "kg",
    "kilo": "kg",
    "kilogram": "kg",
    "lb": "lb",
    "pound": "lb",
}


def read_set(state: JSON, text: str, draft: JSON, library: JSON) -> JSON:
    """Resolve the model's ``draft`` against the active session and the athlete's ``text``.

    Returns ``{"preview": SetPreview, "ignored": [...]}`` when the set is ready to confirm, or
    ``{"question": str, "ignored": [...]}`` when the athlete must say more first. Read-only.
    """
    words = text.strip()
    require(0 < len(words) <= MAX_TEXT_LENGTH, "invalid", "Describe one set in up to 500 characters.")
    session = active_session(state)
    require(session is not None, "invalid", "Start a workout before logging a set.")
    assert session is not None
    if session["status"] != "inProgress":
        return _ask("Resume the session to log sets.", [])

    heard_numbers = spoken_numbers(words)
    heard_words = spoken_words(words)
    values, ignored = _grounded_values(draft, heard_numbers)

    names = _slot_names(session, library)
    today = ", ".join(names.values())
    if _names_only_other_exercises(session, heard_words, names, library):
        return _ask(f"That exercise isn't in today's session. Today: {today}.", ignored)
    slot = _pick_slot(session, draft.get("exercise"), heard_words, names)
    if slot is None:
        return _ask(f"Which exercise was that? Today: {today}.", ignored)
    name = names[slot["id"]]
    if draft.get("exercise") is not None and _fold(draft["exercise"]) != _fold(name):
        ignored.append("exercise")

    reps = values.get("reps")
    if reps is None or not 0 <= reps <= MAX_REPS:
        return _ask(f"How many reps did you do on {name}?", ignored)

    unit = slot["equipment"]["unit"]
    heard_units = {UNIT_WORDS[word] for word in heard_words if word in UNIT_WORDS}
    if "load" in values and heard_units and unit not in heard_units:
        return _ask(f"{name} is recorded in {unit}. Say the load in {unit}.", ignored)

    kind = spoken_kind(heard_words)
    if kind == "working":
        index = _first_open_index(session, slot)
        if index is None:
            count = slot["workingSets"]
            return _ask(f'All {count} working sets of {name} are logged. Say "extra set" to add one.', ignored)
    else:
        index = len(session["logs"])

    preview: JSON = {
        "sessionID": session["id"],
        "slotID": slot["id"],
        "exerciseID": slot["exerciseID"],
        "name": name,
        "index": index,
        "kind": kind,
        "reps": reps,
        "unit": unit,
    }
    for optional in ("load", "rir"):
        if optional in values:
            preview[optional] = values[optional]
    return {"preview": preview, "ignored": ignored}


def spoken_numbers(text: str) -> list[float]:
    """Every number in ``text``: digits (``80``, ``22.5``) and the words zero to twenty.

    Only a point is a decimal separator, so "8,80" is two numbers rather than 8.8.
    """
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]
    numbers.extend(float(NUMBER_WORDS[word]) for word in re.findall(r"[a-z]+", text.casefold()) if word in NUMBER_WORDS)
    return numbers


def spoken_words(text: str) -> set[str]:
    """The singular stems of the letter-only words in ``text`` (``rows`` -> ``row``, ``80kg`` -> ``kg``)."""
    return {_singular(word) for word in re.findall(r"[a-z]+", text.casefold())}


def spoken_kind(heard_words: set[str]) -> str:
    """``warmUp`` or ``extra`` only when the athlete said so; any other set is a working set."""
    if "warm" in heard_words or "warmup" in heard_words:
        return "warmUp"
    if "extra" in heard_words:
        return "extra"
    return "working"


def _grounded_values(draft: JSON, heard_numbers: list[float]) -> tuple[JSON, list[str]]:
    """The draft's reps, load and RIR that the athlete actually said, and the names of the rest.

    Each spoken number backs one field at most, in the order reps, load, RIR: "maybe 6" is six
    reps, not six reps at a load of six.
    """
    values: JSON = {}
    ignored: list[str] = []
    unused = list(heard_numbers)
    for field in ("reps", "load", "rir"):
        value = draft.get(field)
        if value is None:
            continue
        match = next((heard for heard in unused if math.isclose(value, heard, abs_tol=1e-9)), None)
        if match is None:
            ignored.append(field)
        else:
            unused.remove(match)
            values[field] = value
    if "rir" in values and not 0 <= values["rir"] <= MAX_RIR:
        del values["rir"]
        ignored.append("rir")
    return values, ignored


def _pick_slot(session: JSON, named: str | None, heard_words: set[str], names: dict[str, str]) -> JSON | None:
    """The slot the athlete meant, or ``None`` when that is ambiguous.

    A slot is *heard* when the athlete said a word only its name contains. The model's pick
    wins among heard slots; one heard slot wins alone; no heard slot means the next open set,
    or the only slot of a one-exercise session.
    """
    slots: list[JSON] = session["plan"]["slots"]
    heard = [slot for slot in slots if _distinctive_words(slot, slots, names) & heard_words]
    if named is not None:
        for slot in heard:
            if _fold(names[slot["id"]]) == _fold(named):
                return slot
    if len(heard) == 1:
        return heard[0]
    if heard:
        return None
    current = _current_slot(session)
    if current is None and len(slots) == 1:
        return slots[0]
    return current


def _names_only_other_exercises(session: JSON, heard_words: set[str], names: dict[str, str], library: JSON) -> bool:
    """Whether the athlete named a library exercise outside this session and none inside it.

    "bench 80 for 8" in a dumbbell session is a question, not a floor press at 80.
    """
    slots: list[JSON] = session["plan"]["slots"]
    if any(_distinctive_words(slot, slots, names) & heard_words for slot in slots):
        return False
    session_words: set[str] = set()
    for name in names.values():
        session_words |= _name_words(name)
    in_session = {slot["exerciseID"] for slot in slots}
    other_words: set[str] = set()
    for exercise in library["exercises"]:
        if exercise["id"] not in in_session:
            other_words |= _name_words(exercise["name"])
    return bool((other_words - session_words) & heard_words)


def _distinctive_words(slot: JSON, slots: list[JSON], names: dict[str, str]) -> set[str]:
    """Words of this slot's name that no other slot's name shares. Number words never count."""
    own = _name_words(names[slot["id"]])
    for other in slots:
        if other["id"] != slot["id"]:
            own -= _name_words(names[other["id"]])
    return own


def _name_words(name: str) -> set[str]:
    return {word for word in spoken_words(name) if len(word) >= SHORTEST_NAME_WORD and word not in NUMBER_WORDS}


def _current_slot(session: JSON) -> JSON | None:
    """The slot of the first working set, in plan order, that has no log yet."""
    slots: list[JSON] = session["plan"]["slots"]
    for slot in slots:
        if _first_open_index(session, slot) is not None:
            return slot
    return None


def _first_open_index(session: JSON, slot: JSON) -> int | None:
    for index in range(slot["workingSets"]):
        if not has_working_set(session, slot["id"], index):
            return index
    return None


def _slot_names(session: JSON, library: JSON) -> dict[str, str]:
    """Slot id -> the exercise's library name (its id when the library no longer has it)."""
    exercises = exercises_by_id(library)
    names: dict[str, str] = {}
    for slot in session["plan"]["slots"]:
        exercise = exercises.get(slot["exerciseID"])
        names[slot["id"]] = exercise["name"] if exercise else slot["exerciseID"]
    return names


def _singular(word: str) -> str:
    if word.endswith("es") and word[:-2].endswith(("ss", "sh", "ch", "x")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _fold(text: str) -> str:
    return text.strip().casefold()


def _ask(question: str, ignored: list[str]) -> JSON:
    return {"question": question, "ignored": ignored}
