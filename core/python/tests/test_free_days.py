"""Changing free days after onboarding (ADR-025): the first choice is a starting point.

New days and minutes are proposed as a week the athlete accepts; nothing changes before that,
and confirmed loads carry over to the same exercises.
"""

import copy
import unittest

from support import NOW, Athlete, call, result
from test_adaptation import adaptive_library, athlete_on_weekly_plan, command

from ai_trainer.athlete_state import comparison_key
from ai_trainer.errors import DomainError
from ai_trainer.rules.eligibility import decide
from ai_trainer.today import today_status

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


def change(days, minutes=None, option_id=None):
    request = {"kind": "changeDays", "freeDays": days}
    if minutes is not None:
        request["minutes"] = minutes
    if option_id is not None:
        request["optionID"] = option_id
    return request


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.library = adaptive_library()
        self.state = athlete_on_weekly_plan(self.library)

    def test_new_days_propose_a_week_on_those_days_only(self):
        decision = decide(self.state, change([MON, WED, FRI]), self.library, NOW)
        self.assertEqual((decision["outcome"], decision["reason"]), ("proposeChange", "NEW_FREE_DAYS"))
        weekdays = {session["weekday"] for session in decision["week"]["sessions"]}
        self.assertTrue(weekdays <= {MON, WED, FRI})
        self.assertIn("Monday, Wednesday and Friday", decision["explanation"])

    def test_a_chosen_option_is_the_one_proposed(self):
        best = decide(self.state, change([MON, WED, FRI]), self.library, NOW)["week"]
        again = decide(self.state, change([MON, WED, FRI], option_id=best["id"]), self.library, NOW)
        self.assertEqual(again["week"], best)

    def test_no_days_asks_for_one(self):
        self.assertEqual(decide(self.state, change([]), self.library, NOW)["reason"], "DAYS_REQUIRED")

    def test_the_same_days_and_minutes_keep_the_week(self):
        days = self.state["profile"]["freeDays"]
        self.assertEqual(decide(self.state, change(days), self.library, NOW)["reason"], "SAME_DAYS")

    def test_an_option_no_longer_offered_is_not_guessed(self):
        decision = decide(self.state, change([MON, WED, FRI], option_id="no-such-week"), self.library, NOW)
        self.assertEqual(decision["reason"], "WEEK_OPTION_MISSING")

    def test_weekdays_and_minutes_are_checked(self):
        with self.assertRaises(DomainError):
            decide(self.state, change([9]), self.library, NOW)
        with self.assertRaises(DomainError):
            decide(self.state, change([MON], minutes=5), self.library, NOW)

    def test_it_is_the_athletes_own_request_so_a_break_does_not_pause_it(self):
        self.state["statusPeriods"] = [{"id": "away", "kind": "onBreak", "startedAt": NOW - 3600}]
        self.assertEqual(decide(self.state, change([MON, WED, FRI]), self.library, NOW)["reason"], "NEW_FREE_DAYS")

    def test_nothing_changes_before_accept(self):
        before = copy.deepcopy(self.state)
        decide(self.state, change([MON, WED, FRI], minutes=30), self.library, NOW)
        self.assertEqual(self.state, before)


class ContractTests(unittest.TestCase):
    def test_the_request_passes_the_contract_with_and_without_its_optional_fields(self):
        state = Athlete.qualified().state
        for request in (change([MON, WED]), change([MON, WED], minutes=30, option_id="any")):
            payload = {"state": state, "request": request, "permitsFixtures": True, "now": NOW}
            # The pinned fixture has no weekly planner, so the core says so; the shape was accepted.
            self.assertEqual(result("decide", payload)["reason"], "REPLAN_UNAVAILABLE")

    def test_a_malformed_request_is_refused_by_the_contract(self):
        payload = {
            "state": Athlete.qualified().state,
            "request": {"kind": "changeDays"},
            "permitsFixtures": True,
            "now": NOW,
        }
        self.assertEqual(call("decide", payload)["error"]["code"], "invalid")


class AcceptTests(unittest.TestCase):
    def setUp(self):
        self.library = adaptive_library()
        self.state = athlete_on_weekly_plan(self.library)

    def propose_and_accept(self, request):
        state = command(self.state, "requestChange", self.library, request=request)["state"]
        recommendation = state["recommendations"][-1]
        self.assertEqual(recommendation["status"], "proposed")
        return command(state, "acceptRecommendation", self.library, id=recommendation["id"])["state"], recommendation

    def test_accepting_replaces_the_week_and_keeps_the_new_days(self):
        old = copy.deepcopy(self.state["program"])
        state, recommendation = self.propose_and_accept(change([MON, WED, FRI], minutes=30))
        week = recommendation["decision"]["week"]
        self.assertEqual(state["program"]["templateID"], week["id"])
        self.assertEqual((state["profile"]["freeDays"], state["profile"]["minutes"]), ([MON, WED, FRI], 30))
        self.assertEqual(state["previousPrograms"][-1], old)
        self.assertEqual(state["recommendations"][-1]["status"], "applied")

    def test_today_names_the_proposed_week(self):
        state = command(self.state, "requestChange", self.library, request=change([MON, WED, FRI]))["state"]
        titles = [proposal["title"] for proposal in today_status(state, self.library, NOW)["proposals"]]
        week = state["recommendations"][-1]["decision"]["week"]
        self.assertIn(f"Proposed · {week['name']} · {week['sessionsPerWeek']} days a week", titles)

    def test_confirmed_loads_carry_over_to_the_same_exercises(self):
        slot = self.state["program"]["plans"][0]["slots"][0]
        slot["load"] = 22.5
        slot["equipment"]["availableLoads"] = [20.0, 22.5, 25.0]
        state, _ = self.propose_and_accept(change([MON, WED, FRI]))
        carried = [
            candidate
            for plan in state["program"]["plans"]
            for candidate in plan["slots"]
            if comparison_key(candidate) == comparison_key(slot)
        ]
        self.assertTrue(carried, "the exercise is still in the new week")
        for candidate in carried:
            self.assertEqual(candidate["load"], 22.5)
            self.assertEqual(candidate["equipment"]["availableLoads"], [20.0, 22.5, 25.0])
        unconfirmed = [
            candidate
            for plan in state["program"]["plans"]
            for candidate in plan["slots"]
            if comparison_key(candidate) != comparison_key(slot)
        ]
        self.assertTrue(all(candidate.get("load") is None for candidate in unconfirmed), "unknown stays unknown")


if __name__ == "__main__":
    unittest.main()
