"""Weekly programs from the planner (ADR-017): distinct options, the Program, and acceptance.

The library here is the pinned fixture plus test planner blocks and fixture exercises for the
planner's roles, so these tests do not change whenever research updates the shipped content.
"""

import copy
import math
import unittest

from support import NOW, Athlete, uid
from test_week_plans import RANKING, STRUCTURES, WEEKLY

from ai_trainer.commands import reduce_state
from ai_trainer.content import load_library
from ai_trainer.errors import DomainError
from ai_trainer.rules.program import initial_program
from ai_trainer.rules.week_program import option_summaries, week_options

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
IDS = [uid(8000 + index) for index in range(80)]

ROLE_EXERCISES = {
    "UPH": ("dumbbell", "perHand"),
    "UPV": ("dumbbell", "perHand"),
    "ULH": ("dumbbell", "perHand"),
    "ULV": ("machine", "machineSetting"),
    "KD": ("dumbbell", "total"),
    "HH": ("dumbbell", "perHand"),
    "SL": ("dumbbell", "perHand"),
    "EF": ("dumbbell", "perHand"),
    "EE": ("dumbbell", "perHand"),
    "KF": ("machine", "machineSetting"),
    "CALF": ("dumbbell", "perHand"),
}


def planner_library():
    """The fixture library with a test planner and one fixture exercise per planner role."""
    library = copy.deepcopy(load_library(True))
    for role, (kind, basis) in ROLE_EXERCISES.items():
        library["exercises"].append(
            {
                "id": f"test_{role.lower()}",
                "name": f"Test {role} exercise",
                "role": role,
                "equipmentKind": kind,
                "basis": basis,
                "alternatives": [],
                "review": "fixture",
                "contentVersion": "fixture-1",
            }
        )
    structures = copy.deepcopy(STRUCTURES)
    for session_type, definition in structures["sessions"].items():
        definition["name"] = session_type
    structures["splitNames"] = {split: split for split in structures["splits"]}
    library["planner"] = {
        "weekly": {**WEEKLY, "minutesPerSet": {"Hypertrophy": 2.0, "Strength": 2.5}},
        "structures": structures,
        "ranking": {**RANKING, "optionsShown": 3},
        "targets": {
            "Hypertrophy": {"Beginner": 10, "Intermediate": 12},
            "Strength": {"Beginner": 10, "Intermediate": 10},
        },
        "adaptation": {
            "windowDays": 28,
            "minimumPlanAgeDays": 14,
            "missedSessionsPerWeek": 1,
            "extraSessionsPerWeek": 1,
            "endedEarlyForTime": 2,
            "minimumSessionMinutes": 15,
            "habitShare": 0.5,
            "otherDaysShare": 0.5,
        },
    }
    return library


def profile(**overrides):
    base = copy.deepcopy(Athlete.qualified().state["profile"])
    base.update(
        {
            "goal": "Hypertrophy",
            "experience": "Beginner",
            "minutes": 60,
            "equipment": ["dumbbell", "machine"],
            "excludedExercises": [],
            "preferredExercises": [],
        }
    )
    base.update(overrides)
    return base


class WeekOptionTests(unittest.TestCase):
    def test_options_are_distinct_and_capped(self):
        options = week_options(profile(freeDays=[MON, TUE, THU, SAT]), planner_library())
        self.assertLessEqual(len(options), 3)
        shapes = [(option["split"], len(option["sessions"])) for option in options]
        self.assertEqual(len(shapes), len(set(shapes)))

    def test_unknown_weekdays_cap_sessions_at_days_per_week(self):
        options = week_options(profile(daysPerWeek=2), planner_library())
        self.assertTrue(options)
        self.assertTrue(all(len(option["sessions"]) <= 2 for option in options))

    def test_minutes_by_day_apply_to_that_day(self):
        options = week_options(profile(freeDays=[MON, THU], minutesByDay={"0": 20}), planner_library())
        for option in options:
            for session in option["sessions"]:
                self.assertLessEqual(session["minutes"], 20 if session["day"] == MON else 60)

    def test_missing_equipment_leaves_its_roles_out(self):
        options = week_options(profile(freeDays=[MON, WED, FRI], equipment=["dumbbell"]), planner_library())
        roles = {slot["role"] for option in options for session in option["sessions"] for slot in session["slots"]}
        self.assertNotIn("ULV", roles)  # the only vertical pull here is a machine
        self.assertNotIn("KF", roles)

    def test_summaries_describe_each_option(self):
        library = planner_library()
        summary = option_summaries(week_options(profile(freeDays=[MON, WED, FRI]), library), library)[0]
        self.assertEqual(summary["sessionsPerWeek"], len(summary["sessions"]))
        self.assertEqual(summary["weeklyMinutes"], sum(session["minutes"] for session in summary["sessions"]))
        self.assertTrue(set(summary["days"]) <= {MON, WED, FRI})
        self.assertIn(summary["volume"], ("full", "reduced"))


class WeekProgramTests(unittest.TestCase):
    def test_one_plan_per_session_with_weekdays_and_unknown_loads(self):
        library = planner_library()
        athlete = profile(freeDays=[MON, WED, FRI])
        option = week_options(athlete, library)[0]
        program = initial_program(athlete, library, NOW, IDS, option["id"])
        self.assertEqual(program["templateID"], option["id"])
        self.assertEqual([plan["weekday"] for plan in program["plans"]], option["days"])
        for plan, session in zip(program["plans"], option["sessions"], strict=True):
            self.assertEqual(
                [slot["workingSets"] for slot in plan["slots"]], [slot["sets"] for slot in session["slots"]]
            )
            for slot in plan["slots"]:
                self.assertNotIn("load", slot)  # never estimated
                self.assertEqual(len(slot["targets"]), slot["workingSets"])
                self.assertEqual(slot["estimatedMinutes"], math.ceil(slot["workingSets"] * 2.0))

    def test_without_an_option_the_best_week_is_built(self):
        library = planner_library()
        athlete = profile(freeDays=[TUE, THU])
        best = week_options(athlete, library)[0]
        self.assertEqual(initial_program(athlete, library, NOW, IDS)["templateID"], best["id"])

    def test_accepting_rebuilds_the_same_week(self):
        library = planner_library()
        athlete = profile(freeDays=[MON, TUE, THU, SAT])
        option = week_options(athlete, library)[1]
        preview = initial_program(athlete, library, NOW, IDS, option["id"])
        state = Athlete.fresh().state
        payload = {
            "command": "acceptInitialPlan",
            "state": state,
            "arguments": {"profile": athlete, "optionID": option["id"]},
            "permitsFixtures": True,
            "now": NOW,
            "ids": IDS,
        }
        accepted = reduce_state(payload, library)["state"]["program"]
        self.assertEqual(accepted, preview)

    def test_an_option_that_no_longer_fits_is_refused(self):
        library = planner_library()
        option = week_options(profile(freeDays=[MON, TUE, THU, SAT]), library)[0]
        with self.assertRaises(DomainError):
            initial_program(profile(freeDays=[WED]), library, NOW, IDS, option["id"])

    def test_too_little_time_is_a_clear_refusal(self):
        with self.assertRaises(DomainError) as refused:
            initial_program(profile(freeDays=[MON], minutes=10), planner_library(), NOW, IDS)
        self.assertIn("Add a free day or more time", str(refused.exception))

    def test_the_one_session_template_refuses_an_option(self):
        with self.assertRaises(DomainError):
            initial_program(profile(), load_library(True), NOW, IDS, "fullBody:Mon-fullBodyA")


if __name__ == "__main__":
    unittest.main()
