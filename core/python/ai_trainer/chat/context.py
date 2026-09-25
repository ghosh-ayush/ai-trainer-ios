"""Everything one chat answer reads, gathered once, and how the model's draft is grounded (ADR-023).

A number counts only if the athlete's words contain it ("2 hours", "half an hour" and "2 weeks"
are read as minutes and days), and an exercise only if the athlete said a word of its name, the
same rule ``read_set`` applies to a set in words (ADR-015).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from ..athlete_state import active_session, next_plan
from ..citations import Citations
from ..content import exercises_by_id
from ..spoken_sets import NUMBER_WORDS, spoken_numbers, spoken_words
from ..wording import MONTHS_SHORT, WEEKDAY_SHORT, fold

JSON = dict[str, Any]

DAY = 86400.0
MINUTE = 60
REFERENCE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
SHORTEST_NAME_WORD = 3
MINUTES_RANGE = (5, 600)
DAYS_RANGE = (1, 365)


class ChatContext:
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
        earlier: str | None = None,
    ) -> None:
        self.state = state
        self.library = library
        self.citations = Citations(bundle)
        self.now = now
        self.day_start = day_start
        self.utc_offset = utc_offset
        self.text = text.casefold()
        self.words = spoken_words(text)
        self.numbers = spoken_numbers(text)
        # The athlete's previous message, so a follow-up ("and bench?", "why?") keeps its exercise.
        self.earlier_words = spoken_words(earlier) if earlier else set()
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
        return f"{WEEKDAY_SHORT[moment.weekday()]} {moment.day} {MONTHS_SHORT[moment.month - 1]}"

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
        exercise, candidates, dropped = self._grounded_in(self.words, named)
        if exercise is None and not candidates and self.earlier_words:
            # A follow-up names no exercise: the one the athlete named just before still counts.
            exercise, candidates, dropped_earlier = self._grounded_in(self.earlier_words, named)
            dropped = dropped and dropped_earlier
        if dropped:
            ignored.append("exercise")
        return exercise, candidates

    def _grounded_in(self, words: set[str], named: str | None) -> tuple[str | None, list[str], bool]:
        """``(exercise, ambiguous candidates, whether the model's pick was dropped)`` for ``words``."""
        heard = [key for key in self.names if self._distinctive(key) & words]
        mentioned = [key for key in self.names if self._name_words(self.names[key]) & words]
        dropped = False
        if named is not None:
            picked = next((key for key in self.names if fold(self.names[key]) == fold(named)), None)
            if picked is not None and picked in mentioned and (picked in heard or len(mentioned) == 1):
                return picked, [], False
            dropped = picked is None or picked not in mentioned
        if len(heard) == 1:
            return heard[0], [], dropped
        if len(mentioned) == 1:
            return mentioned[0], [], dropped
        return None, heard or mentioned, dropped

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
