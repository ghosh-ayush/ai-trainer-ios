"""The Training Brain: gate order, progression, adjustments and program selection."""

import copy
import unittest

from support import NOW, Athlete, call, exposure, golden_request, result, uid

from ai_trainer.queries import comparable_sessions, working_logs


def athlete_with(*sessions):
    """A fresh athlete whose history is ``(days_ago, reps, rir)`` exposures, oldest first."""
    athlete = Athlete.qualified()
    template = athlete.state["sessions"][0]
    athlete.state["sessions"] = [
        exposure(template, 100 + number, days_ago, reps, rir) for number, (days_ago, reps, rir) in enumerate(sessions)
    ]
    return athlete


class ProgressionTests(unittest.TestCase):
    def test_qualifying_history_proposes_next_step_at_bottom_of_range(self):
        decision = Athlete.qualified().decide()
        self.assertEqual(decision["reason"], "QUALIFYING_EXPOSURES_COMPLETE")
        slot = decision["after"]["slots"][0]
        self.assertEqual((slot["load"], slot["targets"], slot["workingSets"]), (105, [8, 8, 8], 3))
        self.assertEqual(len(decision["evidence"]), 6)

    def test_rep_progression_adds_exactly_one_rep(self):
        decision = athlete_with((1, [9, 8, 8], 2)).decide()
        self.assertEqual(decision["after"]["slots"][0]["targets"], [10, 8, 8])
        self.assertEqual(decision["after"]["slots"][0]["load"], 100)

    def test_evidence_failures_name_their_reason(self):
        cases = {
            "EFFORT_UNKNOWN": athlete_with((1, [10, 10, 10], None)),
            "INCOMPLETE_EXPOSURE": athlete_with((1, [10, 10], 2)),
            "TARGET_NOT_QUALIFIED": athlete_with((1, [10, 10, 10], 0)),
            "HISTORY_STALE": athlete_with((29, [10, 10, 10], 2)),
            "MORE_EXPOSURES_REQUIRED": athlete_with((20, [10, 10, 10], 2), (1, [10, 10, 10], 2)),
        }
        for reason, athlete in cases.items():
            with self.subTest(reason):
                self.assertEqual(athlete.reason(), reason)

    def test_failed_middle_exposure_breaks_the_streak(self):
        athlete = athlete_with((6, [10, 10, 10], 2), (4, [8, 8, 8], 2), (1, [10, 10, 10], 2))
        self.assertEqual(athlete.reason(), "MORE_EXPOSURES_REQUIRED")

    def test_unknown_effort_stays_unknown(self):
        athlete = athlete_with((1, [10, 10, 10], None))
        athlete.decide()
        self.assertNotIn("rir", athlete.state["sessions"][0]["logs"][0])

    def test_modified_or_future_exposure_does_not_qualify(self):
        modified = Athlete.qualified()
        modified.state["sessions"][-1]["plan"]["modified"] = True
        self.assertEqual(modified.reason(), "MODIFIED_EXPOSURE")
        future = Athlete.qualified()
        future.state["sessions"][-1]["startedAt"] = NOW + 1
        self.assertEqual(future.reason(), "MORE_EXPOSURES_REQUIRED")

    def test_equipment_is_never_guessed(self):
        cases = {
            "LOADING_POLICY_UNAVAILABLE": ("basis", "machineSetting"),
            "EQUIPMENT_STEP_UNKNOWN": ("availableLoads", []),
            "INCREMENT_EXCEEDS_BOUND": ("availableLoads", [100, 110]),
            "NO_COMPARABLE_HISTORY": ("id", "different-rack"),
        }
        for reason, (field, value) in cases.items():
            with self.subTest(reason):
                athlete = Athlete.qualified()
                athlete.slot["equipment"][field] = value
                self.assertEqual(athlete.reason(), reason)

    def test_replay_is_deterministic(self):
        athlete = Athlete.qualified()
        for session in athlete.state["sessions"]:
            session["startedAt"] = NOW - 86400
        first = athlete.decide()
        athlete.state["sessions"].reverse()
        self.assertEqual(athlete.decide(), first)


class GateOrderTests(unittest.TestCase):
    def test_pain_beats_qualifying_history(self):
        athlete = Athlete.qualified()
        athlete.state["painExclusions"] = ["bench"]
        self.assertEqual(athlete.reason(), "REPORTED_PAIN")

    def test_exclusion_beats_preference(self):
        athlete = Athlete.qualified()
        athlete.state["profile"]["excludedExercises"] = ["bench"]
        athlete.state["profile"]["preferredExercises"] = ["bench"]
        self.assertEqual(athlete.reason(), "EXERCISE_EXCLUDED")

    def test_fixture_policy_disabled_in_production(self):
        self.assertEqual(Athlete.qualified().decide(permits_fixtures=False)["reason"], "POLICY_NOT_APPROVED")

    def test_active_session_blocks_proposals(self):
        athlete = Athlete.qualified()
        athlete.start()
        self.assertEqual(athlete.reason(), "SESSION_ACTIVE")

    def test_meals_do_not_change_training_decisions(self):
        athlete = Athlete.qualified()
        before = athlete.decide()
        meal = {
            "id": uid(600),
            "revision": 1,
            "name": "Meal",
            "nutrients": {"calories": 100, "protein": 1, "carbs": 1, "fat": 1},
            "occurredAt": NOW,
            "source": "user_confirmed_estimate",
            "timeZone": "UTC",
        }
        athlete.run("saveMeal", meal=meal, asRecipe=False)
        self.assertEqual(athlete.decide(), before)


class AdjustmentTests(unittest.TestCase):
    def test_substitution_clears_load_and_changes_context(self):
        athlete = Athlete.fresh()
        decision = athlete.decide(
            {"kind": "substitute", "slotID": athlete.slot["id"], "alternativeID": "machine_press"}
        )
        self.assertEqual(decision["outcome"], "proposeChange")
        swapped = decision["after"]["slots"][0]
        self.assertNotIn("load", swapped)
        self.assertEqual(swapped["equipment"]["basis"], "machineSetting")
        self.assertNotEqual(swapped["equipment"]["id"], athlete.slot["equipment"]["id"])

    def test_uncurated_substitute_is_withheld(self):
        athlete = Athlete.fresh()
        decision = athlete.decide({"kind": "substitute", "slotID": athlete.slot["id"], "alternativeID": "made_up"})
        self.assertEqual(decision["outcome"], "withholdGuidance")

    def test_shortening_removes_optional_work_only(self):
        athlete = Athlete.fresh()
        extra = copy.deepcopy(athlete.slot)
        extra.update(id=uid(42), optional=True)
        athlete.plan["slots"].append(extra)
        shorter = athlete.decide({"kind": "shorten", "minutes": 20})["after"]
        self.assertEqual(len(shorter["slots"]), 1)
        self.assertEqual((shorter["slots"][0]["restSeconds"], shorter["warmUpMinutes"]), (120, 5))
        self.assertEqual(athlete.reason({"kind": "shorten", "minutes": 5}), "REQUIRED_WORK_DOES_NOT_FIT")


class InitialProgramTests(unittest.TestCase):
    def payload(self, **profile_overrides):
        profile = copy.deepcopy(golden_request()["payload"]["state"]["profile"])
        profile.update(profile_overrides)
        return {"profile": profile, "permitsFixtures": True, "now": NOW, "ids": [uid(n) for n in range(10, 16)]}

    def test_program_is_built_from_the_bundled_template(self):
        program = result("initialProgram", self.payload(preferredExercises=["bench"]))
        slots = program["plans"][0]["slots"]
        self.assertEqual([slot["exerciseID"] for slot in slots], ["bench", "cable_row", "goblet_squat", "db_curl"])
        self.assertEqual([slot["optional"] for slot in slots], [False, False, False, True])
        self.assertTrue(all("load" not in slot and slot["equipment"]["availableLoads"] == [] for slot in slots))
        self.assertEqual(program["templateID"], "FULL_BODY_FIXTURE_01")

    def test_short_sessions_omit_the_accessory(self):
        program = result("initialProgram", self.payload(minutes=45))
        self.assertEqual(len(program["plans"][0]["slots"]), 3)

    def test_unsupported_profiles_and_production_are_refused(self):
        self.assertEqual(call("initialProgram", self.payload(adultConfirmed=False))["error"]["code"], "invalid")
        self.assertEqual(call("initialProgram", self.payload(minutes=30))["error"]["code"], "invalid")
        production = self.payload()
        production["permitsFixtures"] = False
        self.assertEqual(call("initialProgram", production)["error"]["code"], "unsupported")


class HistoryQueryTests(unittest.TestCase):
    def test_comparable_sessions_filter_and_order(self):
        """Newest first; active, skipped, future and differently-equipped sessions excluded."""
        athlete = Athlete.qualified()
        template = athlete.state["sessions"][-1]

        def session(number, days_ago, **overrides):
            candidate = copy.deepcopy(template)
            candidate.update(id=uid(number), startedAt=NOW - days_ago * 86400, **overrides)
            return candidate

        older, newer = session(101, 5), session(102, 1)
        different = session(105, 0)
        different["plan"]["slots"][0]["equipment"]["id"] = "different-rack"
        athlete.state["sessions"] = [
            older,
            session(106, -1),
            session(103, 0, status="skipped"),
            session(104, 0, status="paused"),
            different,
            newer,
        ]
        ordered = comparable_sessions(athlete.state, athlete.slot, NOW)
        self.assertEqual([s["id"] for s in ordered], [newer["id"], older["id"]])
        self.assertEqual([log["index"] for log in working_logs(newer, athlete.slot)], [0, 1, 2])
        older["startedAt"] = newer["startedAt"]  # ties are broken by id
        self.assertEqual(
            [s["id"] for s in comparable_sessions(athlete.state, athlete.slot, NOW)], [older["id"], newer["id"]]
        )


if __name__ == "__main__":
    unittest.main()
