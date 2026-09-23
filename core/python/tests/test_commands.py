"""State commands: workouts, records, meals and the recommendation lifecycle."""

import copy
import unittest

from support import NOW, Athlete, call, check_in, uid


class WorkoutCommandTests(unittest.TestCase):
    def test_repeated_save_creates_one_set(self):
        athlete = Athlete.fresh()
        session = athlete.start()
        arguments = {"sessionID": session["id"], "slotID": athlete.slot["id"], "index": 0, "kind": "working"}
        arguments.update(reps=10, load=100, logID=uid(1), operationID=uid(2))
        athlete.run("saveSet", **arguments)
        athlete.run("saveSet", **arguments)
        self.assertEqual(len(athlete.active_session["logs"]), 1)
        arguments["reps"] = 12
        self.assertEqual(athlete.error_code("saveSet", **arguments), "invalid")

    def test_set_copies_context_from_the_slot_and_keeps_unknowns_absent(self):
        athlete = Athlete.fresh()
        session = athlete.start()
        athlete.save_set(session, 0, reps=0)
        log = athlete.active_session["logs"][0]
        self.assertEqual((log["reps"], log["unit"], log["basis"]), (0, "lb", "total"))
        self.assertTrue(log["contextKey"].startswith("bench|rack-1|lb|total|"))
        self.assertNotIn("load", log)
        self.assertNotIn("rir", log)
        self.assertEqual(athlete.active_session["restEndsAt"], NOW + 120)

    def test_impossible_sets_are_rejected(self):
        athlete = Athlete.fresh()
        session = athlete.start()
        for extra in ({"load": -1}, {"rir": 11}):
            self.assertIn("error", athlete.save_set(session, 0, reps=8, **extra))
        self.assertEqual(athlete.active_session["logs"], [])

    def test_duplicate_working_index_is_not_an_extra_set(self):
        athlete = Athlete.fresh()
        session = athlete.start()
        athlete.save_set(session, 0, reps=8)
        self.assertIn("error", athlete.save_set(session, 0, reps=8))

    def test_unstartable_sessions_leave_state_unchanged(self):
        athlete = Athlete.fresh()
        self.assertEqual(athlete.error_code("start", checkIn=check_in(painReported=True)), "invalid")
        self.assertEqual(athlete.error_code("start", checkIn=check_in(minutes=5)), "invalid")

    def test_early_end_records_omissions_not_zeros(self):
        athlete = Athlete.fresh()
        athlete.start()
        athlete.run("finish", reason="time")
        session = athlete.state["sessions"][-1]
        self.assertEqual(session["status"], "endedEarly")
        self.assertEqual(set(session["omissions"].values()), {"time"})
        self.assertEqual(session["logs"], [])

    def test_skip_does_not_double_the_next_session(self):
        athlete = Athlete.fresh()
        before = copy.deepcopy(athlete.plan)
        athlete.run("skip", checkIn=check_in())
        self.assertEqual(athlete.plan, before)
        self.assertEqual(athlete.state["sessions"][-1]["status"], "skipped")

    def test_excluding_an_active_exercise_pauses_and_blocks_resume(self):
        athlete = Athlete.fresh()
        athlete.start()
        athlete.run("exclude", exerciseID="bench", excluded=True)
        self.assertEqual(athlete.active_session["status"], "paused")
        self.assertIn("bench", athlete.state["profile"]["excludedExercises"])
        self.assertEqual(athlete.error_code("setPaused", paused=False), "invalid")

    def test_configure_load_is_pure_and_deduplicates_steps(self):
        athlete = Athlete.qualified()
        original = copy.deepcopy(athlete.state)
        response = call(
            "stateCommand",
            athlete.payload(
                "configureLoad", {"slotID": athlete.slot["id"], "load": 100, "options": [105, 100, 105]}, NOW
            ),
        )
        state = response["result"]["state"]
        self.assertEqual(state["program"]["plans"][0]["slots"][0]["equipment"]["availableLoads"], [100, 105])
        self.assertEqual(athlete.state, original)
        self.assertEqual(state["revision"], original["revision"])  # only the host's durable commit bumps it

    def test_unknown_load_stays_absent(self):
        athlete = Athlete.qualified()
        athlete.run("configureLoad", slotID=athlete.slot["id"], options=[])
        self.assertNotIn("load", athlete.slot)

    def test_missing_id_budget_is_rejected(self):
        athlete = Athlete.qualified()
        payload = athlete.payload("reportPain", {"exerciseID": "bench"}, NOW)
        payload["ids"] = []
        self.assertIn("error", call("stateCommand", payload))


class RecordCommandTests(unittest.TestCase):
    def test_stale_correction_keeps_both_versions_until_resolved(self):
        athlete = Athlete.qualified()
        session = athlete.state["sessions"][1]
        log = session["logs"][0]
        outcome = athlete.run(
            "correctSet", sessionID=session["id"], logID=log["id"], expectedRevision=0, load=105, reps=12
        )
        self.assertFalse(outcome["value"])
        conflict = athlete.state["conflicts"][0]
        self.assertEqual((conflict["current"]["load"], conflict["incoming"]["load"]), (100, 105))
        self.assertNotIn("rir", conflict["incoming"])
        self.assertEqual(athlete.reason(), "EVIDENCE_CONFLICT")
        athlete.run("resolveConflict", id=conflict["id"], useIncoming=False)
        self.assertEqual(athlete.state["conflicts"], [])
        self.assertEqual(athlete.state["sessions"][1]["logs"][0]["reps"], 10)

    def test_delete_session_removes_dependent_records(self):
        athlete = Athlete.qualified()
        athlete.propose()
        session = athlete.state["sessions"][1]
        athlete.state["audits"] = [{"id": uid(700), "previous": session["logs"][0], "correctedAt": NOW}]
        athlete.run("deleteSession", id=session["id"])
        self.assertEqual(len(athlete.state["sessions"]), 1)
        self.assertEqual(athlete.state["audits"], [])
        self.assertEqual(athlete.state["recommendations"], [])

    def test_program_replacement_keeps_history(self):
        athlete = Athlete.qualified()
        sessions = copy.deepcopy(athlete.state["sessions"])
        athlete.run("acceptInitialPlan", profile=athlete.state["profile"])
        self.assertEqual(athlete.state["sessions"], sessions)
        self.assertEqual(len(athlete.state["previousPrograms"]), 1)

    def test_meal_correction_is_audited_and_stale_edits_rejected(self):
        athlete = Athlete.fresh()
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
        meal["nutrients"]["calories"] = 150
        athlete.run("saveMeal", meal=meal, asRecipe=False)
        self.assertEqual(athlete.state["meals"][0]["revision"], 2)
        self.assertEqual(athlete.state["mealAudits"][0]["previous"]["nutrients"]["calories"], 100)
        self.assertIn("error", athlete.attempt("saveMeal", meal=meal, asRecipe=False))
        athlete.run("deleteMeal", id=meal["id"])
        self.assertEqual((athlete.state["meals"], athlete.state["mealAudits"]), ([], []))


class RecommendationLifecycleTests(unittest.TestCase):
    def test_proposal_is_inert_until_accepted(self):
        athlete = Athlete.qualified()
        recommendation = athlete.propose()
        self.assertEqual(recommendation["request"], {"kind": "progression", "slotID": athlete.slot["id"]})
        self.assertEqual(athlete.slot["load"], 100)
        athlete.run("acceptRecommendation", id=recommendation["id"])
        self.assertEqual(athlete.slot["load"], 105)
        self.assertEqual(athlete.state["recommendations"][0]["status"], "applied")

    def test_acceptance_is_idempotent(self):
        athlete = Athlete.qualified()
        recommendation = athlete.propose()
        athlete.run("acceptRecommendation", id=recommendation["id"])
        athlete.run("acceptRecommendation", id=recommendation["id"])
        applied = [event for event in athlete.state["events"] if event["name"] == "recommendation_applied"]
        self.assertEqual(len(applied), 1)
        self.assertEqual(athlete.slot["load"], 105)

    def test_non_proposals_are_answered_but_not_stored(self):
        athlete = Athlete.fresh()
        outcome = athlete.run("requestChange", request={"kind": "progression", "slotID": athlete.slot["id"]})
        self.assertEqual(outcome["decision"]["reason"], "NO_COMPARABLE_HISTORY")
        self.assertEqual(athlete.state["recommendations"], [])

    def test_correction_expires_a_dependent_proposal(self):
        athlete = Athlete.qualified()
        recommendation = athlete.propose()
        session = athlete.state["sessions"][1]
        log = session["logs"][2]
        athlete.run("correctSet", sessionID=session["id"], logID=log["id"], expectedRevision=1, load=100, reps=8, rir=2)
        self.assertEqual(athlete.state["recommendations"][0]["status"], "expired")
        self.assertEqual(athlete.error_code("acceptRecommendation", id=recommendation["id"]), "staleProposal")
        self.assertEqual(athlete.slot["load"], 100)

    def test_changed_evidence_fails_acceptance(self):
        athlete = Athlete.qualified()
        recommendation = athlete.propose()
        athlete.state["sessions"][-1]["logs"][0]["rir"] = 0
        self.assertEqual(athlete.error_code("acceptRecommendation", id=recommendation["id"]), "staleProposal")

    def test_rejection_does_not_become_a_preference(self):
        athlete = Athlete.qualified()
        profile = copy.deepcopy(athlete.state["profile"])
        recommendation = athlete.propose()
        athlete.run("rejectRecommendation", id=recommendation["id"], reason="prefer_current")
        self.assertEqual(athlete.state["profile"], profile)
        self.assertEqual(athlete.state["recommendations"][0]["status"], "rejected")
        self.assertEqual(athlete.state["recommendations"][0]["rejectionReason"], "prefer_current")

    def test_temporary_override_does_not_replace_the_program(self):
        athlete = Athlete.fresh()
        program = copy.deepcopy(athlete.state["program"])
        recommendation = athlete.propose(
            {"kind": "substitute", "slotID": athlete.slot["id"], "alternativeID": "machine_press"}
        )
        athlete.run("acceptRecommendation", id=recommendation["id"])
        self.assertEqual(athlete.state["program"], program)
        self.assertEqual(athlete.slot["exerciseID"], "machine_press")
        athlete.start()
        athlete.run("finish", reason="time")
        self.assertEqual(athlete.slot["exerciseID"], "bench")


if __name__ == "__main__":
    unittest.main()
