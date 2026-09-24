"""Content bundles: citations are enforced, pending drafts never run, approved content wins."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from support import NOW, call, golden_request, result, uid

from ai_trainer import content


def cited(value, source="paper", locator="Table 1", certainty="moderate"):
    return {"value": value, "source": source, "locator": locator, "certainty": certainty}


def evidence_bundle(review="pending"):
    """A minimal, fully cited bundle built from the fixture's shape."""
    _, fixture = content.read_bundle(content.BUNDLES_DIR / content.FIXTURE_BUNDLE_ID)
    body = copy.deepcopy(fixture)
    body["policy"] = {
        key: (value if key in ("id", "version") else cited(value)) for key, value in fixture["policy"].items()
    }
    body["policy"]["review"] = review
    body["policy"]["version"] = "evidence-1"
    template = fixture["template"]
    body["template"] = {
        "id": template["id"],
        "name": template["name"],
        "supportedGoals": cited(template["supportedGoals"]),
        "minDaysPerWeek": cited(template["minDaysPerWeek"]),
        "maxDaysPerWeek": cited(template["maxDaysPerWeek"]),
        "minSessionMinutes": {
            "value": template["minSessionMinutes"],
            "source": "owner",
            "rationale": "Fits the slots.",
        },
        "warmUpMinutes": cited(template["warmUpMinutes"]),
        "requiredRoles": cited(template["requiredRoles"]),
        "accessory": {
            "exerciseID": "db_curl",
            "equipmentKind": "dumbbell",
            "minSessionMinutes": cited(template["accessory"]["minSessionMinutes"]),
        },
        "slot": {
            "protocolID": "EV_1",
            **{key: cited(value) for key, value in template["slot"].items() if key != "protocolID"},
        },
    }
    for exercise in body["exercises"]:
        exercise["review"] = review
        exercise["contentVersion"] = "evidence-1"
        exercise["sources"] = [{"source": "paper", "locator": "Section 3"}]
    manifest = {
        "id": "evidence-test",
        "version": "evidence-1",
        "review": review,
        "evidenceBasis": "Test bundle.",
        "sources": {"paper": {"citation": "Author A. Title. Journal. 2026.", "doi": "10.0000/test"}},
    }
    if review == "approved":
        manifest["approval"] = {
            "approvedBy": "Owner",
            "approvedOn": "2026-09-23",
            "basis": "Published evidence (ADR-006).",
        }
    return manifest, body


class BundleValidationTests(unittest.TestCase):
    def test_every_shipped_bundle_is_well_formed(self):
        for bundle_id, (manifest, body) in content.all_bundles().items():
            with self.subTest(bundle_id):
                self.assertEqual(content.bundle_problems(manifest, body), [])

    def test_at_most_one_bundle_is_approved(self):
        approved = [m["id"] for m, _ in content.all_bundles().values() if m["review"] == "approved"]
        self.assertLessEqual(len(approved), 1, approved)

    def test_a_fully_cited_bundle_passes(self):
        self.assertEqual(content.bundle_problems(*evidence_bundle()), [])

    def test_uncited_values_are_refused(self):
        manifest, body = evidence_bundle()
        body["template"]["slot"]["restSeconds"] = 120
        body["policy"]["minimumRIR"]["locator"] = ""
        body["exercises"][0]["sources"] = []
        problems = content.bundle_problems(manifest, body)
        self.assertTrue(any("template.slot.restSeconds needs a source" in p for p in problems), problems)
        self.assertTrue(any("policy.minimumRIR: say where" in p for p in problems), problems)
        self.assertTrue(any("name at least one source" in p for p in problems), problems)

    def test_unknown_sources_and_grades_are_refused(self):
        manifest, body = evidence_bundle()
        body["policy"]["historyDays"] = cited(28, source="blog")
        body["policy"]["maximumGapDays"] = cited(14, certainty="probably")
        body["template"]["warmUpMinutes"] = {"value": 5, "source": "owner"}
        problems = " | ".join(content.bundle_problems(manifest, body))
        self.assertIn("unknown source 'blog'", problems)
        self.assertIn("certainty must be one of", problems)
        self.assertIn("owner decision needs a rationale", problems)

    def test_approval_needs_a_record(self):
        manifest, body = evidence_bundle("approved")
        del manifest["approval"]
        self.assertTrue(any("approval.approvedBy" in p for p in content.bundle_problems(manifest, body)))

    def test_resolve_leaves_only_plain_values(self):
        _, body = evidence_bundle()
        resolved = content.resolve(body)
        self.assertEqual(resolved["policy"]["requiredExposures"], 2)
        self.assertEqual(resolved["template"]["slot"]["workingSets"], 3)
        self.assertEqual(resolved["template"]["minSessionMinutes"], 41)


class BundleSelectionTests(unittest.TestCase):
    """Runs against a temporary bundles directory so the shipped selection is untouched."""

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        shutil.copytree(content.BUNDLES_DIR / content.FIXTURE_BUNDLE_ID, self.directory / content.FIXTURE_BUNDLE_ID)
        self.original = content.BUNDLES_DIR
        content.BUNDLES_DIR = self.directory
        content._active_bundle.cache_clear()

    def tearDown(self):
        content.BUNDLES_DIR = self.original
        content._active_bundle.cache_clear()
        shutil.rmtree(self.directory)

    def write(self, manifest, body):
        target = self.directory / manifest["id"]
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        (target / "content.json").write_text(json.dumps(body))
        content._active_bundle.cache_clear()

    def test_pending_bundle_never_runs(self):
        self.write(*evidence_bundle("pending"))
        self.assertEqual(content.load_library(True)["policy"]["version"], "fixture-1")

    def test_approved_bundle_wins_even_in_debug_and_runs_in_release(self):
        self.write(*evidence_bundle("approved"))
        for permits in (True, False):
            library = content.load_library(permits)
            self.assertEqual(library["policy"]["version"], "evidence-1")
            self.assertTrue(content.policy_is_enabled(library))

    def test_malformed_approved_bundle_is_ignored(self):
        manifest, body = evidence_bundle("approved")
        body["template"]["slot"]["restSeconds"] = 120  # uncited
        self.write(manifest, body)
        self.assertEqual(content.load_library(True)["policy"]["version"], "fixture-1")

    def test_goal_specific_prescriptions_are_used(self):
        manifest, body = evidence_bundle("approved")
        strength = {key: copy.deepcopy(value) for key, value in body["template"]["slot"].items()}
        strength["lowerReps"], strength["upperReps"] = cited(3), cited(6)
        body["template"]["slotByGoal"] = {"Strength": strength}
        self.write(manifest, body)
        profile = copy.deepcopy(golden_request()["payload"]["state"]["profile"])
        payload = {"profile": profile, "permitsFixtures": False, "now": NOW, "ids": [uid(n) for n in range(10, 16)]}
        profile["goal"] = "Strength"
        slot = result("initialProgram", payload)["plans"][0]["slots"][0]
        self.assertEqual((slot["lowerReps"], slot["upperReps"], slot["targets"]), (3, 6, [3, 3, 3]))
        profile["goal"] = "Hypertrophy"
        slot = result("initialProgram", payload)["plans"][0]["slots"][0]
        self.assertEqual((slot["lowerReps"], slot["upperReps"]), (8, 10))

    def test_evidence_draft_runs_once_approved(self):
        """The shipped pending draft, approved in a scratch copy: it builds programs and honours the contract."""
        manifest, body = content.read_bundle(self.original / "evidence-1")
        self.assertEqual(manifest["review"], "pending")
        manifest["review"] = body["policy"]["review"] = "approved"
        manifest["approval"] = {"approvedBy": "Test", "approvedOn": "2026-09-23", "basis": "Scratch copy."}
        for exercise in body["exercises"]:
            exercise["review"] = "approved"
        self.write(manifest, body)

        library = result("library", {"permitsFixtures": False})
        self.assertEqual(library["policy"]["version"], "evidence-1")
        self.assertTrue(all("sources" not in exercise for exercise in library["exercises"]))

        profile = copy.deepcopy(golden_request()["payload"]["state"]["profile"])
        payload = {"profile": profile, "permitsFixtures": False, "now": NOW, "ids": [uid(n) for n in range(10, 16)]}
        for goal, rest in (("Hypertrophy", 90), ("Strength", 120)):
            profile["goal"] = goal
            plan = result("initialProgram", payload)["plans"][0]
            self.assertEqual(len(plan["slots"]), 4, goal)  # three required roles and the accessory at 60 minutes
            self.assertEqual({slot["restSeconds"] for slot in plan["slots"]}, {rest}, goal)
        profile["daysPerWeek"] = 4
        self.assertEqual(call("initialProgram", payload)["error"]["code"], "invalid")


if __name__ == "__main__":
    unittest.main()
