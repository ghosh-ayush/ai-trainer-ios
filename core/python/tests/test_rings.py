"""Muscle rings (ADR-020): logged sets per major muscle this local week, against the target."""

import copy
import math
import unittest

from support import NOW, Athlete, uid
from test_week_program import IDS, planner_library, profile

from ai_trainer.content import load_library
from ai_trainer.rings import local_week_start, muscle_rings
from ai_trainer.rules.adaptation import local_weekday
from ai_trainer.rules.program import initial_program

DAY = 86400.0
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
UTC = 0


def weekly_state(library):
    state = Athlete.fresh().state
    athlete = profile(freeDays=[MON, WED, FRI])
    state["profile"] = athlete
    state["program"] = initial_program(athlete, library, NOW - 30 * DAY, IDS)
    return state


def log_sets(state, role, count, occurred_at, kind="working", reps=8):
    """A session holding ``count`` sets of the first slot training ``role``."""
    plan = next(
        p for p in state["program"]["plans"] if any(s["exerciseID"] == f"test_{role.lower()}" for s in p["slots"])
    )
    slot = next(s for s in plan["slots"] if s["exerciseID"] == f"test_{role.lower()}")
    session = copy.deepcopy(Athlete.qualified().state["sessions"][0])
    template = session["logs"][0]
    session.update(
        id=uid(8800 + len(state["sessions"])), plan=copy.deepcopy(plan), startedAt=occurred_at, status="completed"
    )
    session["logs"] = []
    for index in range(count):
        entry = copy.deepcopy(template)
        entry.update(
            id=uid(8900 + len(state["sessions"]) * 10 + index),
            prescriptionID=slot["id"],
            kind=kind,
            reps=reps,
            index=index,
            occurredAt=occurred_at,
        )
        session["logs"].append(entry)
    state["sessions"].append(session)
    return state


def ring(rings, muscle):
    return next(item for item in rings["muscles"] if item["muscle"] == muscle)


class MuscleRingTests(unittest.TestCase):
    def setUp(self):
        self.library = planner_library()
        self.monday = local_week_start(NOW, None, UTC)

    def test_logged_sets_count_fully_for_the_main_muscle_and_half_for_helpers(self):
        state = log_sets(weekly_state(self.library), "UPH", 3, self.monday + 3600)
        rings = muscle_rings(state, self.library, NOW, None, UTC)
        self.assertEqual(ring(rings, "chest")["done"], 3)
        self.assertEqual(ring(rings, "shoulders")["done"], 1.5)
        self.assertEqual(ring(rings, "quadriceps")["done"], 0)
        self.assertEqual(ring(rings, "chest")["target"], 10)

    def test_warm_ups_zero_rep_attempts_and_last_week_do_not_count(self):
        state = weekly_state(self.library)
        log_sets(state, "UPH", 2, self.monday + 3600, kind="warmUp")
        log_sets(state, "UPH", 2, self.monday + 3600, reps=0)
        log_sets(state, "UPH", 4, self.monday - 3600)  # Sunday evening, last week
        self.assertEqual(ring(muscle_rings(state, self.library, NOW, None, UTC), "chest")["done"], 0)

    def test_planned_is_what_the_accepted_week_prescribes(self):
        state = weekly_state(self.library)
        expected = 0.0
        for plan in state["program"]["plans"]:
            for slot in plan["slots"]:
                if slot["exerciseID"] == "test_uph":
                    expected += slot["workingSets"]
        self.assertEqual(ring(muscle_rings(state, self.library, NOW, None, UTC), "chest")["planned"], expected)

    def test_the_week_starts_on_the_athletes_local_monday(self):
        offset = -5 * 3600
        start = local_week_start(NOW, None, offset)
        self.assertEqual(local_weekday(start, offset), MON)
        self.assertEqual((start + offset) % DAY, 0)  # local midnight
        self.assertLessEqual(start, NOW)
        self.assertLess(NOW - start, 7 * DAY)

    def test_no_rings_without_an_offset_or_a_weekly_planner(self):
        state = weekly_state(self.library)
        self.assertIsNone(muscle_rings(state, self.library, NOW, None, None))
        self.assertIsNone(muscle_rings(Athlete.qualified().state, load_library(True), NOW, None, UTC))

    def test_the_host_day_start_is_used_when_given(self):
        state = log_sets(weekly_state(self.library), "UPH", 1, self.monday + 3600)
        day_start = math.floor(NOW / DAY) * DAY
        rings = muscle_rings(state, self.library, NOW, day_start, UTC)
        self.assertEqual(rings["weekStart"], day_start - local_weekday(NOW, UTC) * DAY)


if __name__ == "__main__":
    unittest.main()
