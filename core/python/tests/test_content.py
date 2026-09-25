"""Content bundles: citations and source quality are enforced, drafts never run, approved content wins."""

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from support import NOW, call, golden_request, result, uid

from ai_trainer import content, contracts


def cited(value, source="paper", locator="Table 1", certainty="moderate"):
    return {"value": value, "source": source, "locator": locator, "certainty": certainty}


def evidence_bundle(review="draft"):
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
        "sources": {
            "paper": {
                "citation": "Author A. Title. Journal. 2026.",
                "doi": "10.0000/test",
                "design": "metaAnalysis",
                "fullTextRead": True,
            }
        },
    }
    if review == "approved":
        manifest["verification"] = {"method": "Automated evidence gate (ADR-014).", "verifiedOn": "2026-09-23"}
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

    def test_a_single_study_cannot_carry_moderate_certainty(self):
        manifest, body = evidence_bundle()
        manifest["sources"]["paper"]["design"] = "randomisedTrial"
        problems = content.bundle_problems(manifest, body)
        self.assertTrue(any("a randomisedTrial supports at most low certainty" in p for p in problems), problems)

    def test_approved_needs_a_verification_record_not_a_person(self):
        manifest, body = evidence_bundle("approved")
        self.assertEqual(content.bundle_problems(manifest, body), [])
        del manifest["verification"]
        self.assertTrue(any("verification.method" in p for p in content.bundle_problems(manifest, body)))

    def test_internet_content_is_never_a_source(self):
        """AGENTS.md rule 1: only peer-reviewed research with a DOI or PMID qualifies."""
        manifest, body = evidence_bundle()
        manifest["sources"]["video"] = {"citation": "Best exercises ranked (YouTube).", "design": "video"}
        manifest["sources"]["preprint"] = {
            "citation": "Author B. Preprint. 2026.",
            "doi": "10.51224/x",
            "design": "preprint",
            "fullTextRead": True,
        }
        problems = " | ".join(content.bundle_problems(manifest, body))
        self.assertIn("manifest.sources.video needs a doi or a pmid", problems)
        self.assertIn("manifest.sources.video.design must be one of", problems)
        self.assertIn("manifest.sources.video.fullTextRead", problems)
        self.assertIn("manifest.sources.preprint.design must be one of", problems)

    def test_a_preprint_or_fake_identifier_never_passes_even_with_a_qualifying_design(self):
        manifest, body = evidence_bundle()
        manifest["sources"]["sneaky"] = {
            "citation": "Doe J. Rest intervals. SportRxiv. 2025.",
            "doi": "10.51224/SRXIV.999",
            "design": "metaAnalysis",
            "fullTextRead": True,
        }
        manifest["sources"]["video"] = {
            "citation": "Best exercises (video).",
            "doi": "youtube.com/watch?v=x",
            "design": "randomisedTrial",
            "fullTextRead": True,
        }
        problems = " | ".join(content.bundle_problems(manifest, body))
        self.assertIn("manifest.sources.sneaky is a preprint", problems)
        self.assertIn("manifest.sources.video.doi is not a DOI", problems)

    def test_exercise_citations_need_a_published_locator(self):
        manifest, body = evidence_bundle()
        body["exercises"][0]["sources"] = [{"source": "paper"}]
        body["exercises"][1]["sources"] = [{"source": "paper", "locator": "SportRxiv preprint v1, Table 3"}]
        problems = " | ".join(content.bundle_problems(manifest, body))
        self.assertIn("say where in the source", problems)
        self.assertIn("not a preprint", problems)

    def test_resolve_leaves_only_plain_values(self):
        _, body = evidence_bundle()
        resolved = content.resolve(body)
        self.assertEqual(resolved["policy"]["requiredExposures"], 2)
        self.assertEqual(resolved["template"]["slot"]["workingSets"], 3)
        self.assertEqual(resolved["template"]["minSessionMinutes"], 41)


class BundleSelectionTests(unittest.TestCase):
    """Runs against a temporary bundles directory so the shipped selection is untouched."""

    def setUp(self):
        self.pinned = os.environ.pop(content.PINNED_BUNDLE_ENV, None)
        self.directory = Path(tempfile.mkdtemp())
        shutil.copytree(content.BUNDLES_DIR / content.FIXTURE_BUNDLE_ID, self.directory / content.FIXTURE_BUNDLE_ID)
        self.original = content.BUNDLES_DIR
        content.BUNDLES_DIR = self.directory
        content._active_bundle.cache_clear()

    def tearDown(self):
        os.environ.pop(content.PINNED_BUNDLE_ENV, None)
        if self.pinned is not None:
            os.environ[content.PINNED_BUNDLE_ENV] = self.pinned
        content.BUNDLES_DIR = self.original
        content._active_bundle.cache_clear()
        shutil.rmtree(self.directory)

    def write(self, manifest, body):
        target = self.directory / manifest["id"]
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        (target / "content.json").write_text(json.dumps(body))
        content._active_bundle.cache_clear()

    def test_draft_bundle_never_runs(self):
        self.write(*evidence_bundle("draft"))
        self.assertEqual(content.load_library(True)["policy"]["version"], "fixture-1")

    def test_approved_bundle_wins_even_in_debug_and_runs_in_release(self):
        self.write(*evidence_bundle("approved"))
        for permits in (True, False):
            library = content.load_library(permits)
            self.assertEqual(library["policy"]["version"], "evidence-1")
            self.assertTrue(content.policy_is_enabled(library))

    def test_a_pinned_fixture_wins_but_stays_debug_only(self):
        self.write(*evidence_bundle("approved"))
        os.environ[content.PINNED_BUNDLE_ENV] = content.FIXTURE_BUNDLE_ID
        content._active_bundle.cache_clear()
        self.assertEqual(content.load_library(True)["policy"]["version"], "fixture-1")
        self.assertFalse(content.policy_is_enabled(content.load_library(False)))

    def test_a_draft_cannot_be_pinned(self):
        manifest, body = evidence_bundle("draft")
        self.write(manifest, body)
        os.environ[content.PINNED_BUNDLE_ENV] = manifest["id"]
        content._active_bundle.cache_clear()
        with self.assertRaises(ValueError):
            content.load_library(True)

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

    def test_shipped_evidence_bundle_runs_without_anyone_approving_it(self):
        """ADR-014/017: the approved evidence bundle builds weekly programs in release, within the contract."""
        manifest, body = content.read_bundle(self.original / "evidence-2")
        self.assertEqual(manifest["review"], "approved")
        self.assertNotIn("approval", manifest)
        self.write(manifest, body)

        library = result("library", {"permitsFixtures": False})
        self.assertEqual(library["policy"]["version"], "evidence-2")
        self.assertTrue(all("sources" not in exercise for exercise in library["exercises"]))

        profile = copy.deepcopy(golden_request()["payload"]["state"]["profile"])
        payload = {"profile": profile, "permitsFixtures": False, "now": NOW, "ids": [uid(n) for n in range(10, 90)]}
        for goal, rest in (("Hypertrophy", 90), ("Strength", 120)):
            profile["goal"] = goal
            program = result("initialProgram", payload)
            self.assertTrue(1 <= len(program["plans"]) <= profile["daysPerWeek"], goal)
            for plan in program["plans"]:
                self.assertIn(plan["weekday"], range(7))
                self.assertEqual({slot["restSeconds"] for slot in plan["slots"]}, {rest}, goal)
                self.assertTrue(all("load" not in slot for slot in plan["slots"]))  # never estimated
            contracts.validate(call("initialProgram", payload), contracts.RESPONSE, contracts.RESPONSE)
        profile["daysPerWeek"] = 7
        response = call("weekOptions", {"profile": profile, "permitsFixtures": False})
        contracts.validate(response, contracts.RESPONSE, contracts.RESPONSE)  # what Swift decodes
        options = response["result"]
        self.assertTrue(options)
        self.assertLessEqual(len(options), 3)
        self.assertTrue(all(option["sessionsPerWeek"] <= 6 for option in options))  # no qualifying 7-day trial

    def test_superseded_bundle_never_runs(self):
        manifest, _ = content.read_bundle(self.original / "evidence-1")
        self.assertEqual((manifest["review"], manifest.get("supersededBy")), ("disabled", "evidence-2"))


class RoleNameTests(unittest.TestCase):
    """The host shows movement roles in the bundle's words, not a table of its own."""

    def test_every_planner_role_of_the_shipped_bundle_has_a_name(self):
        _, raw = content.all_bundles()["evidence-2"]
        plain = content.resolve(raw)
        library = {**{key: plain[key] for key in ("exercises", "policy", "planner")}, "permitsFixtures": False}
        names = content.public_library(library)["roleNames"]
        self.assertEqual(set(names), set(plain["planner"]["structures"]["roles"]))
        self.assertEqual((names["KD"], names["HH"], names["UPH"]), ("Squat", "Hip hinge", "Horizontal press"))
        roles_in_use = {exercise["role"] for exercise in plain["exercises"]}
        self.assertTrue(roles_in_use <= set(names), "every exercise's role has a name")

    def test_content_without_a_weekly_planner_names_no_roles(self):
        library = result("library", {"permitsFixtures": True})
        self.assertEqual(library["roleNames"], {})


if __name__ == "__main__":
    unittest.main()
