"""Adapting the week to attendance (ADR-018): a proposal from logged sessions, accepted or not.

Uses the planner test library (pinned fixture plus test planner blocks), so these tests do not
change whenever research updates the shipped content.
"""

import copy
import math
import unittest

from support import NOW, Athlete, uid
from test_week_program import IDS, planner_library, profile

from ai_trainer.commands import reduce_state
from ai_trainer.content import load_library
from ai_trainer.errors import DomainError
from ai_trainer.rules.adaptation import local_weekday
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


def on_weekdays(state, weekdays, weeks=4, status="completed", minutes=30, time_limited=False):
    """Log sessions on the given weekdays (UTC offset 0) for ``weeks`` weeks inside the replan window."""
    template = copy.deepcopy(Athlete.qualified().state["sessions"][0])
    first_day = math.floor(state["program"]["acceptedAt"] / DAY) + 1
    number = len(state["sessions"])
    for week in range(weeks):
        for weekday in weekdays:
            day = first_day + week * 7 + (weekday - first_day) % 7
            started = day * DAY + 3600
            if started > NOW:
                continue
            session = copy.deepcopy(template)
            session.update(id=uid(7500 + number), startedAt=started, endedAt=started + minutes * 60, status=status)
            if time_limited:
                session["status"] = "endedEarly"
                session["omissions"] = {f"{uid(1)}:2": "time"}
            state["sessions"].append(session)
            number += 1
    return state


def replan_at_utc(state, library):
    return decide(state, {"kind": "replan", "utcOffset": 0}, library, NOW)


class WeekdayTests(unittest.TestCase):
    def test_the_reference_epoch_was_a_monday(self):
        self.assertEqual(local_weekday(0, 0), MON)
        self.assertEqual(local_weekday(3 * 3600, -5 * 3600), SUN)  # 03:00 UTC Monday is Sunday evening at UTC-5
        self.assertEqual(local_weekday(23 * 3600, 2 * 3600), TUE)


class DriftTests(unittest.TestCase):
    """ADR-018's other drifts: more sessions, time-limited sessions, other weekdays."""

    def test_training_more_often_proposes_a_bigger_week_on_the_days_you_train(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        planned = len(state["program"]["plans"])
        on_weekdays(state, [MON, TUE, WED, THU, SAT])
        result = replan_at_utc(state, library)
        self.assertEqual(result["reason"], "MORE_SESSIONS_REPLAN", result["explanation"])
        self.assertGreater(result["week"]["sessionsPerWeek"], planned)
        self.assertIn(WED, result["week"]["days"])  # a day the athlete trains on, though not listed as free
        self.assertIn("more than the", result["explanation"])

    def test_more_sessions_without_known_weekdays_cannot_go_past_the_free_days(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        on_weekdays(state, [MON, TUE, WED, THU, SAT])
        result = decide(state, REPLAN, library, NOW)  # no UTC offset: weekday habits stay unknown
        self.assertEqual(result["reason"], "NO_BETTER_WEEK")

    def test_sessions_ending_early_for_time_propose_shorter_sessions(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        planned_days = [plan["weekday"] for plan in state["program"]["plans"]]
        on_weekdays(state, planned_days[:2])
        on_weekdays(state, planned_days[2:], minutes=27, time_limited=True)
        result = replan_at_utc(state, library)
        self.assertEqual(result["reason"], "SHORTER_SESSIONS_REPLAN", result["explanation"])
        self.assertTrue(all(session["minutes"] <= 25 for session in result["week"]["sessions"]))
        self.assertIn("ended early for time; they lasted about 25 minutes", result["explanation"])

    def test_training_on_other_days_moves_the_week_onto_them(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        planned = len(state["program"]["plans"])
        habits = [MON, WED, FRI, SUN][:planned]
        on_weekdays(state, habits)
        result = replan_at_utc(state, library)
        self.assertEqual(result["reason"], "TRAINING_DAYS_REPLAN", result["explanation"])
        self.assertEqual(result["week"]["sessionsPerWeek"], planned)
        on_habit = sum(1 for day in result["week"]["days"] if day in habits)
        self.assertGreaterEqual(on_habit, planned - 1)
        self.assertIn("You have mostly trained on", result["explanation"])

    def test_a_weekday_replan_is_accepted_with_the_same_offset(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        on_weekdays(state, [MON, WED, FRI, SUN][: len(state["program"]["plans"])])
        request = {"kind": "replan", "utcOffset": 0}
        state = command(state, "requestChange", library, request=request)["state"]
        week = state["recommendations"][-1]["decision"]["week"]
        state = command(state, "acceptRecommendation", library, id=state["recommendations"][-1]["id"])["state"]
        self.assertEqual(state["program"]["templateID"], week["id"])

    def test_today_offers_a_weekday_replan_only_when_it_knows_the_offset(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        on_weekdays(state, [MON, WED, FRI, SUN][: len(state["program"]["plans"])])
        self.assertTrue(today_status(state, library, NOW, 0).get("autoReplan"))
        self.assertNotIn("autoReplan", today_status(state, library, NOW))  # unknown offset: no weekday drift


def athlete_plan_sessions(library):
    """The sessions a week in the four-free-day plan these tests start from."""
    return initial_program(profile(freeDays=[MON, TUE, THU, SAT]), library, NOW, IDS)["plans"]


if __name__ == "__main__":
    unittest.main()
