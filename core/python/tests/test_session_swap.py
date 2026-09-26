"""Doing a different session today (ADR-026): proposed, recovery-checked, and swapped on Accept.

The chosen session becomes today's and the one it replaces takes its weekday. Before accepting,
the proposal warns when a muscle trained yesterday would go over the planner's cited back-to-back
limit, and lists muscles trained in the last 72 hours as the app's own, uncited notice.
"""

import copy
import unittest

from support import NOW, Athlete, result
from test_adaptation import adaptive_library, athlete_on_weekly_plan, command
from test_rings import log_sets

from ai_trainer.rules.eligibility import decide
from ai_trainer.today import today_status

DAY = 86400.0
HOUR = 3600.0


def swap_to(plan, utc_offset=0):
    return {"kind": "swapSession", "planID": plan["id"], "utcOffset": utc_offset}


class SwapTests(unittest.TestCase):
    def setUp(self):
        self.library = adaptive_library()
        self.state = athlete_on_weekly_plan(self.library)
        self.plans = self.state["program"]["plans"]
        self.lower, self.upper = self.plans[0], self.plans[1]  # Monday lower is next; Tuesday upper
        self.state["sessions"] = []  # recovery checks read only the sets each test logs

    def test_another_session_is_proposed_with_where_the_skipped_one_goes(self):
        decision = decide(self.state, swap_to(self.upper), self.library, NOW)
        self.assertEqual((decision["outcome"], decision["reason"]), ("proposeChange", "SESSION_SWAP"))
        self.assertEqual(decision["after"]["id"], self.upper["id"])
        self.assertTrue(decision["explanation"].startswith("Do upper today; lower moves to Tuesday."))

    def test_the_next_session_or_an_unknown_one_is_not_a_swap(self):
        self.assertEqual(decide(self.state, swap_to(self.lower), self.library, NOW)["reason"], "ALREADY_NEXT")
        missing = {"kind": "swapSession", "planID": "00000000-0000-0000-0000-00000000dead"}
        self.assertEqual(decide(self.state, missing, self.library, NOW)["reason"], "SESSION_MISSING")

    def test_accepting_swaps_the_two_sessions_and_their_days(self):
        state = command(self.state, "requestChange", self.library, request=swap_to(self.upper))["state"]
        recommendation = state["recommendations"][-1]
        titles = [proposal["title"] for proposal in today_status(state, self.library, NOW)["proposals"]]
        self.assertIn("Proposed · upper today", titles)
        state = command(state, "acceptRecommendation", self.library, id=recommendation["id"])["state"]
        plans = state["program"]["plans"]
        today = plans[state["program"]["sequenceIndex"]]
        self.assertEqual((today["id"], today["weekday"]), (self.upper["id"], self.lower["weekday"]))
        moved = next(plan for plan in plans if plan["id"] == self.lower["id"])
        self.assertEqual(moved["weekday"], self.upper["weekday"])
        self.assertEqual(sorted(plan["id"] for plan in plans), sorted(plan["id"] for plan in self.plans))
        self.assertEqual(state["recommendations"][-1]["status"], "applied")

    def test_nothing_changes_before_accept(self):
        before = copy.deepcopy(self.state)
        decide(self.state, swap_to(self.upper), self.library, NOW)
        self.assertEqual(self.state, before)

    def test_a_break_does_not_pause_the_athletes_own_choice(self):
        self.state["statusPeriods"] = [{"id": "away", "kind": "onBreak", "startedAt": NOW - HOUR}]
        self.assertEqual(decide(self.state, swap_to(self.upper), self.library, NOW)["reason"], "SESSION_SWAP")


class RecoveryNoteTests(unittest.TestCase):
    def setUp(self):
        self.library = adaptive_library()
        self.state = athlete_on_weekly_plan(self.library)
        self.state["sessions"] = []
        self.upper = self.state["program"]["plans"][1]

    def explanation(self):
        return decide(self.state, swap_to(self.upper), self.library, NOW)["explanation"]

    def test_a_muscle_trained_yesterday_that_would_go_over_the_cited_limit_is_a_warning(self):
        log_sets(self.state, "UPH", 3, NOW - DAY)  # a press yesterday: chest, and half credit for its helpers
        text = self.explanation()
        # Helper muscles count half, as the weekly planner counts them (ADR-017).
        self.assertIn(
            "Heads-up: chest (5 sets), triceps (6 sets) and shoulders (5.5 sets) were trained yesterday", text
        )
        self.assertIn("the planner's limit of 3 sets for a muscle on the day after it was trained", text)

    def test_within_the_limit_or_two_days_ago_there_is_no_warning(self):
        log_sets(self.state, "UPH", 3, NOW - 2.5 * DAY)
        self.assertNotIn("Heads-up", self.explanation())

    def test_the_72_hour_notice_is_labelled_as_the_apps_own_rule(self):
        self.library["planner"]["weekly"]["recoveryNoticeHours"] = 72
        log_sets(self.state, "UPH", 3, NOW - 2.5 * DAY)  # 60 hours ago: outside yesterday, inside 72 h
        text = self.explanation()
        self.assertIn("Trained in the last 72 hours: chest (60 h ago)", text)
        self.assertIn("72 hours is the app's own notice; no study shows that long a rest is needed.", text)
        self.assertNotIn("Heads-up", text)

    def test_content_without_the_notice_value_shows_none(self):
        log_sets(self.state, "UPH", 3, NOW - 2.5 * DAY)
        self.assertNotIn("72 hours", self.explanation())

    def test_warm_ups_do_not_count(self):
        log_sets(self.state, "UPH", 3, NOW - DAY, kind="warmUp")
        self.assertNotIn("Heads-up", self.explanation())


class ContractTests(unittest.TestCase):
    def test_the_request_passes_the_contract(self):
        athlete = Athlete.qualified()
        plan = athlete.state["program"]["plans"][0]
        for request in (swap_to(plan), {"kind": "swapSession", "planID": plan["id"]}):
            payload = {"state": athlete.state, "request": request, "permitsFixtures": True, "now": NOW}
            self.assertEqual(result("decide", payload)["reason"], "ALREADY_NEXT")


if __name__ == "__main__":
    unittest.main()
