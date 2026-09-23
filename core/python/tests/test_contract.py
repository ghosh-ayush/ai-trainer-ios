"""The Swift ⇄ Python boundary: golden fixture, fail-closed validation, stateless operations."""

import copy
import json
import unittest

from support import FIXTURES, NOW, ROOT, call, golden_request, result, uid

from ai_trainer import contracts
from ai_trainer.api import dispatch_json


class GoldenContractTests(unittest.TestCase):
    def test_golden_response_and_no_input_mutation(self):
        request = golden_request()
        before = copy.deepcopy(request)
        expected = json.loads((FIXTURES / "qualifying-response.json").read_text())
        self.assertEqual(json.loads(dispatch_json(json.dumps(request))), expected)
        self.assertEqual(request, before)
        contracts.validate(expected, contracts.RESPONSE, contracts.RESPONSE)

    def test_unsupported_version_and_unknown_operation(self):
        request = golden_request()
        request["schemaVersion"] = "2.0"
        self.assertEqual(json.loads(dispatch_json(json.dumps(request)))["error"]["code"], "unsupported")
        self.assertIn("error", call("unknown", {}))

    def test_malformed_payloads_fail_closed(self):
        mutations = [
            lambda p: p["request"].update(minutes=True),
            lambda p: p["state"]["program"]["plans"][0]["slots"][0].update(workingSets=0),
            lambda p: p.update(now=float("nan")),
            lambda p: p["request"].update(slotID="bad-id"),
            lambda p: p.update(library={}),  # the host no longer sends content
        ]
        for mutate in mutations:
            payload = golden_request()["payload"]
            mutate(payload)
            self.assertIn("error", call("decide", payload))

    def test_request_kinds_are_strict(self):
        payload = golden_request()["payload"]
        payload["request"] = {"kind": "shorten", "slotID": uid(1)}
        self.assertIn("error", call("decide", payload))


class StatelessOperationTests(unittest.TestCase):
    def test_library_is_bundled_and_gated(self):
        library = result("library", {"permitsFixtures": True})
        self.assertEqual(library["policy"]["review"], "fixture")
        self.assertEqual(len({exercise["id"] for exercise in library["exercises"]}), len(library["exercises"]))
        self.assertNotIn("template", library)  # host displays content; it does not get the template
        self.assertFalse(result("library", {"permitsFixtures": False})["permitsFixtures"])

    def test_nutrition_scaling_and_overflow(self):
        nutrients = {"calories": 200, "protein": 10, "carbs": 20, "fat": 5}
        self.assertEqual(result("nutrients", {"nutrients": nutrients, "servings": 2})["calories"], 400)
        self.assertIn("error", call("nutrients", {"nutrients": nutrients, "servings": 1e308}))
        self.assertIn("error", call("nutrients", {"nutrients": nutrients, "servings": -1}))

    def test_recovery_is_unassessed_even_with_samples(self):
        observations = [{"id": uid(500), "title": "HRV", "value": "50 ms", "date": NOW, "source": "HealthKit"}]
        assessment = result("recovery", {"observations": observations})
        self.assertEqual(assessment["status"], "unassessed")
        self.assertEqual(assessment["observations"], observations)


class BundledResourceTests(unittest.TestCase):
    def test_exercise_catalog_is_well_formed_with_unique_ids(self):
        """The app decodes the catalog directly, so its shape is checked here instead of at runtime."""
        path = ROOT / "apps/ios/Sources/AITrainerCore/Resources/exercises.json"
        records = json.loads(path.read_text())
        for record in records:
            contracts.validate(record, contracts.REQUEST["$defs"]["CatalogExercise"])
        self.assertEqual(len({record["id"] for record in records}), len(records))
        self.assertEqual(len(records), 876)


class MigrationTests(unittest.TestCase):
    def saved_v1(self):
        state = golden_request()["payload"]["state"]
        state["schemaVersion"] = 1
        decision = json.loads((FIXTURES / "qualifying-response.json").read_text())["result"]
        state["recommendations"] = [
            {
                "id": uid(700),
                "stateRevision": 0,
                "contextRevision": 0,
                "targetPlanID": state["program"]["plans"][0]["id"],
                "targetPlanRevision": 1,
                "request": {"substitute": {"_0": uid(1), "_1": "machine_press"}},
                "decision": decision,
                "policyVersion": "fixture-1",
                "createdAt": NOW,
                "status": "proposed",
            }
        ]
        return state

    def test_v1_stored_request_becomes_explicit(self):
        migrated = result("migrateState", {"state": self.saved_v1()})
        self.assertEqual(migrated["schemaVersion"], 2)
        self.assertEqual(
            migrated["recommendations"][0]["request"],
            {"kind": "substitute", "slotID": uid(1), "alternativeID": "machine_press"},
        )

    def test_current_state_passes_through_unchanged(self):
        state = golden_request()["payload"]["state"]
        self.assertEqual(result("migrateState", {"state": state}), state)

    def test_newer_or_corrupt_state_fails_closed(self):
        newer = golden_request()["payload"]["state"]
        newer["schemaVersion"] = 3
        self.assertEqual(call("migrateState", {"state": newer})["error"]["code"], "unsupported")
        corrupt = golden_request()["payload"]["state"]
        del corrupt["sessions"]
        self.assertEqual(call("migrateState", {"state": corrupt})["error"]["code"], "invalid")


if __name__ == "__main__":
    unittest.main()
