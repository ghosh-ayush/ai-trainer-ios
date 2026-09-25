"""Training status (ADR-019): a break, illness or injury pauses what the app proposes on its own.

A status never changes the plan. It stops automatic proposals while it lasts, keeps the
athlete's own requests working, and its days never count as missed sessions.
"""

import unittest

from support import NOW, Athlete, progression, result
from test_adaptation import REPLAN, adaptive_library, athlete_on_weekly_plan

from ai_trainer.athlete_state import active_status, status_seconds
from ai_trainer.rules.eligibility import decide
from ai_trainer.today import today_status

DAY = 86400.0


def views_today(athlete):
    return result("views", {"state": athlete.state, "permitsFixtures": True, "now": NOW})["today"]


class StatusCommandTests(unittest.TestCase):
    def test_a_status_starts_now_and_ends_at_its_end(self):
        athlete = Athlete.qualified()
        athlete.run("setStatus", status="sick", endsAt=NOW + 3 * DAY)
        period = athlete.state["statusPeriods"][-1]
        self.assertEqual((period["kind"], period["startedAt"], period["endsAt"]), ("sick", NOW, NOW + 3 * DAY))
        self.assertIs(active_status(athlete.state, NOW + DAY), period)
        self.assertIsNone(active_status(athlete.state, NOW + 3 * DAY))  # over at its end, without a tap

    def test_an_end_in_the_past_is_refused(self):
        athlete = Athlete.qualified()
        self.assertEqual(athlete.error_code("setStatus", status="onBreak", endsAt=NOW - 60), "invalid")

    def test_a_new_status_ends_the_current_one(self):
        athlete = Athlete.qualified()
        athlete.run("setStatus", status="onBreak")
        athlete.run("setStatus", status="injured", now=NOW + DAY)
        first, second = athlete.state["statusPeriods"]
        self.assertEqual(first["endedAt"], NOW + DAY)
        self.assertEqual(active_status(athlete.state, NOW + 2 * DAY), second)

    def test_i_am_back_ends_it_and_needs_one_to_end(self):
        athlete = Athlete.qualified()
        self.assertEqual(athlete.error_code("endStatus"), "invalid")
        athlete.run("setStatus", status="onBreak")
        athlete.run("endStatus", now=NOW + DAY)
        self.assertEqual(athlete.state["statusPeriods"][-1]["endedAt"], NOW + DAY)
        self.assertIsNone(active_status(athlete.state, NOW + DAY))

    def test_overlapping_periods_are_counted_once(self):
        state = {
            "statusPeriods": [
                {"id": "a", "kind": "onBreak", "startedAt": 0.0, "endedAt": 4 * DAY},
                {"id": "b", "kind": "sick", "startedAt": 2 * DAY, "endsAt": 6 * DAY},
            ]
        }
        self.assertEqual(status_seconds(state, 0.0, 10 * DAY), 6 * DAY)
        self.assertEqual(status_seconds(state, 5 * DAY, 10 * DAY), 1 * DAY)


class StatusPausesProposalsTests(unittest.TestCase):
    def test_progression_waits_but_the_athletes_own_requests_still_run(self):
        athlete = Athlete.qualified()
        self.assertEqual(athlete.reason(), "QUALIFYING_EXPOSURES_COMPLETE")
        athlete.run("setStatus", status="sick")
        self.assertEqual(athlete.reason(), "STATUS_PAUSED")
        self.assertNotEqual(athlete.reason({"kind": "shorten", "minutes": 20}), "STATUS_PAUSED")

    def test_today_shows_the_status_and_requests_nothing(self):
        athlete = Athlete.qualified()
        self.assertEqual(views_today(athlete)["autoRequest"], athlete.slot["id"])
        athlete.run("setStatus", status="onBreak", endsAt=NOW + 7 * DAY)
        today = views_today(athlete)
        self.assertIsNone(today["autoRequest"])
        self.assertEqual(today["status"]["kind"], "onBreak")
        self.assertEqual(athlete.decide(progression(athlete.slot["id"]))["reason"], "STATUS_PAUSED")


class StatusAndAttendanceTests(unittest.TestCase):
    """A holiday is not a missed session (the gap this status was built to close)."""

    def holiday(self, with_status):
        library = adaptive_library()
        planned = 4
        state = athlete_on_weekly_plan(library, per_week=0)
        accepted = state["program"]["acceptedAt"]
        # Two weeks of full attendance, then two weeks away with nothing logged.
        full = athlete_on_weekly_plan(library, weeks_ago=4, per_week=planned)
        state["sessions"] = [s for s in full["sessions"] if s["startedAt"] < accepted + 14 * DAY]
        if with_status:
            state["statusPeriods"] = [
                {"id": "holiday", "kind": "onBreak", "startedAt": accepted + 14 * DAY, "endedAt": NOW}
            ]
        return decide(state, REPLAN, library, NOW)

    def test_without_a_status_the_absence_reads_as_missed_sessions(self):
        self.assertEqual(self.holiday(with_status=False)["reason"], "ADHERENCE_REPLAN")

    def test_with_a_break_marked_the_week_stays(self):
        self.assertEqual(self.holiday(with_status=True)["reason"], "FOLLOWING_THE_PLAN")

    def test_a_status_covering_most_of_the_window_leaves_too_little_to_judge(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=0)
        accepted = state["program"]["acceptedAt"]
        state["statusPeriods"] = [{"id": "away", "kind": "sick", "startedAt": accepted + 3 * DAY, "endedAt": NOW}]
        self.assertEqual(decide(state, REPLAN, library, NOW)["reason"], "REPLAN_NEEDS_HISTORY")

    def test_no_replan_is_offered_while_away(self):
        library = adaptive_library()
        state = athlete_on_weekly_plan(library, per_week=1)
        self.assertTrue(today_status(state, library, NOW).get("autoReplan"))
        state["statusPeriods"] = [{"id": "now", "kind": "injured", "startedAt": NOW - DAY}]
        today = today_status(state, library, NOW)
        self.assertNotIn("autoReplan", today)
        self.assertEqual(today["status"]["kind"], "injured")


if __name__ == "__main__":
    unittest.main()
