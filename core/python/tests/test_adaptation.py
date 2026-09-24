"""Adapting the week to attendance (ADR-018): a proposal from logged sessions, accepted or not.

Uses the planner test library (pinned fixture plus test planner blocks), so these tests do not
change whenever research updates the shipped content.
"""

import copy
import unittest

from support import NOW, Athlete, uid
from test_week_program import IDS, planner_library, profile

from ai_trainer.commands import reduce_state
from ai_trainer.content import load_library
from ai_trainer.errors import DomainError
from ai_trainer.rules.eligibility import decide
from ai_trainer.rules.program import initial_program
from ai_trainer.today import today_status

DAY = 86400.0
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
REPLAN = {"kind": "replan"}


def adaptive_library():
    """The planner test library; its ``adaptation`` block mirrors the bundle's thresholds."""
    return planner_library()


def athlete_on_weekly_plan(library, weeks_ago=4, per_week=4, status="completed"):
    """A state following a four-day plan accepted ``weeks_ago`` weeks ago, with ``per_week`` sessions logged."""
    state = Athlete.fresh().state
    athlete = profile(freeDays=[MON, TUE, THU, SAT])
    accepted_at = NOW - weeks_ago * 7 * DAY
    state["profile"] = athlete
    state["program"] = initial_program(athlete, library, accepted_at, IDS)
    template = copy.deepcopy(Athlete.qualified().state["sessions"][0])
    number = 0
    for week in range(weeks_ago):
        for index in range(per_week):
            started = accepted_at + week * 7 * DAY + (index + 1) * DAY + 3600  # inside the day-anchored window
            session = copy.deepcopy(template)
            session.update(id=uid(7000 + number), startedAt=started, endedAt=started + 1800, status=status)
            state["sessions"].append(session)
            number += 1
    return state


def command(state, name, library, **arguments):
    payload = {
        "command": name,
        "state": state,
        "arguments": arguments,
        "permitsFixtures": True,
        "now": NOW,
        "ids": [uid(9000 + index) for index in range(80)],
    }
    return reduce_state(payload, library)


class ReplanDecisionTests(unittest.TestCase):
    def test_following_the_plan_keeps_it(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=len(athlete_plan_sessions(library)))
        self.assertEqual(decide(state, REPLAN, library, NOW)["reason"], "FOLLOWING_THE_PLAN")

    def test_a_new_week_is_not_judged_yet(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, weeks_ago=1, per_week=0)
        self.assertEqual(decide(state, REPLAN, library, NOW)["reason"], "REPLAN_NEEDS_HISTORY")

    def test_missed_sessions_propose_a_week_that_fits(self):
        library = adaptive_library()
        planned = len(athlete_plan_sessions(library))
        state = athlete_on_weekly_plan(library, per_week=planned - 2)
        result = decide(state, REPLAN, library, NOW)
        self.assertEqual((result["outcome"], result["reason"]), ("proposeChange", "ADHERENCE_REPLAN"))
        self.assertLessEqual(result["week"]["sessionsPerWeek"], planned - 2)
        self.assertIn(f"about {planned - 2} of {planned} planned sessions", result["explanation"])
        self.assertNotIn("after", result)  # the week becomes a program only on acceptance

    def test_nothing_logged_counts_as_missed(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        result = decide(state, REPLAN, library, NOW)
        self.assertEqual(result["reason"], "ADHERENCE_REPLAN")
        self.assertEqual(result["week"]["sessionsPerWeek"], 1)  # at least one session, never zero

    def test_skipped_sessions_are_not_done(self):
        library = adaptive_library()
        planned = len(athlete_plan_sessions(library))
        state = athlete_on_weekly_plan(library, per_week=planned, status="skipped")
        self.assertEqual(decide(state, REPLAN, library, NOW)["reason"], "ADHERENCE_REPLAN")

    def test_the_decision_is_repeatable(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=1)
        self.assertEqual(decide(state, REPLAN, library, NOW), decide(state, REPLAN, library, NOW))

    def test_without_a_planner_nothing_adapts(self):
        library = load_library(True)
        state = Athlete.qualified().state
        self.assertEqual(decide(state, REPLAN, library, NOW)["reason"], "REPLAN_UNAVAILABLE")
        self.assertNotIn("autoReplan", today_status(state, library, NOW))


class ReplanLifecycleTests(unittest.TestCase):
    def test_accepting_replaces_the_program_and_keeps_the_old_one(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=2)
        old = copy.deepcopy(state["program"])
        state = command(state, "requestChange", library, request=REPLAN)["state"]
        recommendation = state["recommendations"][-1]
        self.assertEqual(recommendation["status"], "proposed")
        week = recommendation["decision"]["week"]
        state = command(state, "acceptRecommendation", library, id=recommendation["id"])["state"]
        self.assertEqual(state["program"]["templateID"], week["id"])
        self.assertEqual(len(state["program"]["plans"]), week["sessionsPerWeek"])
        self.assertEqual(state["previousPrograms"][-1], old)
        self.assertEqual(state["recommendations"][-1]["status"], "applied")

    def test_a_proposal_made_earlier_the_same_day_can_still_be_accepted(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=2)
        morning = (NOW // DAY) * DAY + 3600
        payload = {
            "command": "requestChange",
            "state": state,
            "arguments": {"request": REPLAN},
            "permitsFixtures": True,
            "now": morning,
            "ids": [uid(9500 + n) for n in range(80)],
        }
        state = reduce_state(payload, library)["state"]
        evening = morning + 14 * 3600
        payload = {
            "command": "acceptRecommendation",
            "state": state,
            "arguments": {"id": state["recommendations"][-1]["id"]},
            "permitsFixtures": True,
            "now": evening,
            "ids": [uid(9600 + n) for n in range(80)],
        }
        self.assertEqual(reduce_state(payload, library)["state"]["recommendations"][-1]["status"], "applied")

    def test_a_changed_context_makes_the_replan_stale(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=2)
        state = command(state, "requestChange", library, request=REPLAN)["state"]
        state["contextRevision"] += 1
        with self.assertRaises(DomainError) as refused:
            command(state, "acceptRecommendation", library, id=state["recommendations"][-1]["id"])
        self.assertEqual(refused.exception.code, "staleProposal")

    def test_today_offers_it_once_and_not_after_rejection(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=1)
        self.assertTrue(today_status(state, library, NOW).get("autoReplan"))
        state = command(state, "requestChange", library, request=REPLAN)["state"]
        status = today_status(state, library, NOW)
        self.assertNotIn("autoReplan", status)
        self.assertTrue(status["proposals"][0]["title"].startswith("Proposed · "))
        state = command(state, "rejectRecommendation", library, id=state["recommendations"][-1]["id"])["state"]
        self.assertNotIn("autoReplan", today_status(state, library, NOW))


def athlete_plan_sessions(library):
    """The sessions a week in the four-free-day plan these tests start from."""
    return initial_program(profile(freeDays=[MON, TUE, THU, SAT]), library, NOW, IDS)["plans"]


if __name__ == "__main__":
    unittest.main()
