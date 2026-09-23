import copy
import json
import unittest
from pathlib import Path

from ai_trainer.contracts import validate
from ai_trainer.service import dispatch_json

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "shared/fixtures/v1"


def uid(n):
    return f"00000000-0000-0000-0000-{n:012d}"


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads((FIXTURES / "qualifying-request.json").read_text())
        self.p = self.request["payload"]
        self.state = self.p["state"]
        self.slot = self.state["program"]["plans"][0]["slots"][0]

    def run_request(self, request=None):
        return json.loads(dispatch_json(json.dumps(request or self.request)))

    def reason(self):
        return self.run_request()["result"]["reason"]

    def test_golden_contract_and_no_input_mutation(self):
        before = copy.deepcopy(self.request)
        expected = json.loads((FIXTURES / "qualifying-response.json").read_text())
        self.assertEqual(self.run_request(), expected)
        self.assertEqual(self.request, before)
        response_schema = json.loads((ROOT / "shared/schemas/v1/response.schema.json").read_text())
        validate(expected, response_schema, response_schema)

    def test_unknown_effort_stays_unknown(self):
        self.state["sessions"][-1]["logs"][0].pop("rir")
        self.assertEqual(self.reason(), "EFFORT_UNKNOWN")
        self.assertNotIn("rir", self.state["sessions"][-1]["logs"][0])

    def test_pain_overrides_qualifying_history(self):
        self.state["painExclusions"] = ["bench"]
        self.assertEqual(self.reason(), "REPORTED_PAIN")

    def test_fixture_disabled_in_production(self):
        self.p["library"]["permitsFixtures"] = False
        self.assertEqual(self.reason(), "POLICY_NOT_APPROVED")

    def test_future_evidence_ignored(self):
        self.state["sessions"][-1]["startedAt"] = self.p["now"] + 1
        self.assertEqual(self.reason(), "MORE_EXPOSURES_REQUIRED")

    def test_modified_exposure_not_qualified(self):
        self.state["sessions"][-1]["plan"]["modified"] = True
        self.assertEqual(self.reason(), "MODIFIED_EXPOSURE")

    def test_machine_loading_not_guessed(self):
        self.slot["equipment"]["basis"] = "machineSetting"
        self.assertEqual(self.reason(), "LOADING_POLICY_UNAVAILABLE")

    def test_missing_step_not_guessed(self):
        self.slot["equipment"]["availableLoads"] = []
        self.assertEqual(self.reason(), "EQUIPMENT_STEP_UNKNOWN")

    def test_large_step_not_rounded_up(self):
        self.slot["equipment"]["availableLoads"] = [100, 110]
        self.assertEqual(self.reason(), "INCREMENT_EXCEEDS_BOUND")

    def test_deterministic_history_tie_break(self):
        for s in self.state["sessions"]:
            s["startedAt"] = self.p["now"] - 86400
        first = self.run_request()
        self.state["sessions"].reverse()
        self.assertEqual(first, self.run_request())

    def test_invalid_version_and_unknown_operation(self):
        self.request["schemaVersion"] = "2.0"
        self.assertEqual(self.run_request()["error"]["code"], "unsupported")
        self.request["schemaVersion"] = "1.0"
        self.request["operation"] = "unknown"
        self.assertIn("error", self.run_request())

    def test_malformed_payloads_fail_closed(self):
        for mutate in [
            lambda: self.p["request"].update(minutes=True),
            lambda: self.slot.update(workingSets=0),
            lambda: self.p.update(now=float("nan")),
            lambda: self.p["request"].update(slotID="bad-id"),
        ]:
            original = copy.deepcopy(self.request)
            mutate()
            self.assertIn("error", self.run_request())
            self.request = original
            self.p = self.request["payload"]
            self.slot = self.p["state"]["program"]["plans"][0]["slots"][0]

    def recommendation(self, operation, state=None, **extra):
        p = dict(
            operation=operation,
            state=state or self.state,
            library=self.p["library"],
            now=self.p["now"],
            ids=[uid(800), uid(801)],
            **extra,
        )
        return self.run_request(dict(schemaVersion="1.0", operation="recommendation", payload=p))

    def proposal(self):
        return self.recommendation("request", request=self.p["request"])["result"]

    def test_recommendation_is_proposal_until_accepted(self):
        result = self.proposal()
        state = result["state"]
        self.assertEqual(state["program"]["plans"][0]["slots"][0]["load"], 100)
        accepted = self.recommendation("accept", state=state, id=uid(800), request=self.p["request"])["result"]["state"]
        self.assertEqual(accepted["program"]["plans"][0]["slots"][0]["load"], 105)
        self.assertEqual(accepted["recommendations"][0]["status"], "applied")

    def test_changed_evidence_expires_acceptance(self):
        state = self.proposal()["state"]
        state["sessions"][-1]["logs"][0]["rir"] = 0
        self.assertEqual(
            self.recommendation("accept", state=state, id=uid(800), request=self.p["request"])["error"]["code"],
            "staleProposal",
        )

    def test_rejection_does_not_become_preference(self):
        state = self.proposal()["state"]
        result = self.recommendation("reject", state=state, id=uid(800), reason="prefer_current")["result"]["state"]
        self.assertEqual(result["profile"], self.state["profile"])
        self.assertEqual(result["recommendations"][0]["status"], "rejected")

    def test_nutrition_scaling_and_overflow(self):
        req = dict(
            schemaVersion="1.0",
            operation="nutrients",
            payload=dict(nutrients=dict(calories=200, protein=10, carbs=20, fat=5), servings=2),
        )
        self.assertEqual(self.run_request(req)["result"]["calories"], 400)
        req["payload"]["servings"] = 1e308
        self.assertIn("error", self.run_request(req))

    def test_duplicate_catalog_rejected(self):
        e = dict(
            id="x",
            name="X",
            level="beginner",
            primaryMuscles=[],
            secondaryMuscles=[],
            instructions=[],
            category="strength",
            images=[],
        )
        req = dict(schemaVersion="1.0", operation="catalog", payload=dict(exercises=[e, e]))
        self.assertIn("error", self.run_request(req))

    def test_recovery_is_unassessed_even_with_samples(self):
        observations = [dict(id=uid(500), title="HRV", value="50 ms", date=self.p["now"], source="HealthKit")]
        req = dict(schemaVersion="1.0", operation="recovery", payload=dict(observations=observations))
        result = self.run_request(req)["result"]
        self.assertEqual(result["status"], "unassessed")
        self.assertEqual(result["observations"], observations)

    def test_schema_copies_are_current(self):
        for name in ("request", "response"):
            self.assertEqual(
                (ROOT / f"shared/schemas/v1/{name}.schema.json").read_bytes(),
                (ROOT / f"core/python/ai_trainer/{name}.schema.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()


class StateReducerTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((FIXTURES / "qualifying-request.json").read_text())["payload"]
        self.state = self.base["state"]
        self.slot = self.state["program"]["plans"][0]["slots"][0]

    def command(self, name, arguments, state=None):
        request = dict(
            schemaVersion="1.0",
            operation="stateCommand",
            payload=dict(
                command=name,
                state=state or self.state,
                arguments=arguments,
                library=self.base["library"],
                now=self.base["now"],
                ids=[uid(900 + i) for i in range(10)],
            ),
        )
        return json.loads(dispatch_json(json.dumps(request)))

    def test_configuration_is_pure_and_deduplicates_steps(self):
        result = self.command("configureLoad", dict(slotID=self.slot["id"], load=100, options=[105, 100, 105]))[
            "result"
        ]["state"]
        self.assertEqual(result["program"]["plans"][0]["slots"][0]["equipment"]["availableLoads"], [100, 105])
        self.assertEqual(self.slot["equipment"]["availableLoads"], [100, 105, 110])
        self.assertEqual(result["revision"], self.state["revision"])  # Only host durable commit increments revision.

    def test_unknown_load_stays_absent(self):
        result = self.command("configureLoad", dict(slotID=self.slot["id"], options=[]))["result"]["state"]
        self.assertNotIn("load", result["program"]["plans"][0]["slots"][0])

    def test_failed_precondition_keeps_input_unchanged(self):
        before = copy.deepcopy(self.state)
        result = self.command(
            "start", dict(checkIn=dict(painReported=True, unavailableEquipment=[], occurredAt=self.base["now"]))
        )
        self.assertIn("error", result)
        self.assertEqual(self.state, before)

    def test_stale_correction_preserves_both_values(self):
        session = self.state["sessions"][0]
        log = session["logs"][0]
        result = self.command(
            "correctSet", dict(sessionID=session["id"], logID=log["id"], expectedRevision=0, load=105, reps=9)
        )["result"]
        self.assertFalse(result["value"])
        self.assertTrue(result["state"]["sessions"][0]["logs"][0]["conflicted"])
        conflict = result["state"]["conflicts"][0]
        self.assertEqual(conflict["current"]["load"], 100)
        self.assertEqual(conflict["incoming"]["load"], 105)
        self.assertNotIn("rir", conflict["incoming"])

    def test_meal_correction_is_audited(self):
        meal = dict(
            id=uid(600),
            revision=1,
            name="Meal",
            nutrients=dict(calories=100, protein=1, carbs=1, fat=1),
            occurredAt=self.base["now"],
            source="user_confirmed_estimate",
            timeZone="UTC",
        )
        state = self.command("saveMeal", dict(meal=meal, asRecipe=False))["result"]["state"]
        meal["nutrients"]["calories"] = 150
        result = self.command("saveMeal", dict(meal=meal, asRecipe=False), state=state)["result"]["state"]
        self.assertEqual(result["meals"][0]["revision"], 2)
        self.assertEqual(result["mealAudits"][0]["previous"]["nutrients"]["calories"], 100)

    def test_delete_removes_related_evidence(self):
        session = self.state["sessions"][0]
        self.state["audits"] = [dict(id=uid(700), previous=session["logs"][0], correctedAt=self.base["now"])]
        result = self.command("deleteSession", dict(id=session["id"]))["result"]["state"]
        self.assertEqual(len(result["sessions"]), 1)
        self.assertEqual(result["audits"], [])

    def test_missing_id_budget_rejected_before_reducer(self):
        request = dict(
            schemaVersion="1.0",
            operation="stateCommand",
            payload=dict(
                command="reportPain",
                state=self.state,
                arguments=dict(exerciseID="bench"),
                library=self.base["library"],
                now=self.base["now"],
                ids=[],
            ),
        )
        self.assertIn("error", json.loads(dispatch_json(json.dumps(request))))

    def test_explicit_exclusion_pauses_active_session(self):
        self.state["sessions"][-1]["status"] = "inProgress"
        state = self.command("exclude", dict(exerciseID="bench", excluded=True))["result"]["state"]
        self.assertEqual(state["sessions"][-1]["status"], "paused")
        self.assertIn("bench", state["profile"]["excludedExercises"])
