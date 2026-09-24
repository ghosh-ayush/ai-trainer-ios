"""Research annotations on the descriptive catalog: cited, in sync, and kept out of guidance."""

import copy
import json
import unittest

from support import ROOT

from ai_trainer import catalog_evidence, contracts

CATALOG_PATH = ROOT / "apps/ios/Sources/AITrainerCore/Resources/exercises.json"
EVIDENCE_PATH = ROOT / "docs/research/exercise-evidence.json"
CORE_DIR = ROOT / "core/python/ai_trainer"


def catalog() -> list:
    """The bundled catalog as shipped."""
    return json.loads(CATALOG_PATH.read_text())


def evidence() -> dict:
    """The reviewed evidence file the catalog is annotated from."""
    return json.loads(EVIDENCE_PATH.read_text())


class EvidenceFileTests(unittest.TestCase):
    def test_every_finding_is_cited_graded_and_mapped_to_real_catalog_ids(self):
        self.assertEqual(catalog_evidence.evidence_problems(evidence(), catalog()), [])

    def test_bundled_catalog_matches_the_evidence_file(self):
        """``scripts/annotate_catalog.py`` has been run after the last evidence change."""
        records = catalog()
        expected = catalog_evidence.annotate(records, evidence())
        self.assertEqual(records, expected)

    def test_annotated_records_still_satisfy_the_contract(self):
        definition = contracts.REQUEST["$defs"]["CatalogExercise"]
        annotated = [record for record in catalog() if "evidence" in record]
        self.assertTrue(annotated, "the evidence file should annotate at least one catalog record")
        for record in annotated:
            contracts.validate(record, definition)


class AnnotateTests(unittest.TestCase):
    def sample(self) -> tuple[list, dict]:
        records = [
            {
                "id": "A",
                "name": "A",
                "level": "beginner",
                "primaryMuscles": ["chest"],
                "secondaryMuscles": [],
                "instructions": [],
                "category": "strength",
                "images": [],
            },
            {
                "id": "B",
                "name": "B",
                "level": "beginner",
                "primaryMuscles": ["lats"],
                "secondaryMuscles": [],
                "instructions": [],
                "category": "strength",
                "images": [],
            },
        ]
        file = {
            "sources": {
                "S1": {
                    "citation": "Author A. Title. Journal. 2020.",
                    "doi": "10.1000/x",
                    "design": "randomisedTrial",
                    "fullTextRead": True,
                }
            },
            "findings": [
                {
                    "id": "F1",
                    "source": "S1",
                    "outcome": "hypertrophy",
                    "muscles": ["chest"],
                    "finding": "A grew the chest more than B.",
                    "locator": "Results",
                    "certainty": "low",
                    "fullTextRead": True,
                    "exercises": [
                        {"name": "a", "result": "favoured", "catalogIDs": ["A"]},
                        {"name": "b", "result": "lessFavoured", "catalogIDs": []},
                    ],
                }
            ],
        }
        return records, file

    def test_only_mapped_records_gain_evidence_and_upstream_fields_are_untouched(self):
        records, file = self.sample()
        before = copy.deepcopy(records)
        annotated = catalog_evidence.annotate(records, file)
        self.assertEqual(records, before)
        self.assertEqual(annotated[0]["evidence"][0]["result"], "favoured")
        self.assertEqual(annotated[0]["evidence"][0]["doi"], "10.1000/x")
        self.assertNotIn("evidence", annotated[1])
        self.assertEqual({k: v for k, v in annotated[0].items() if k != "evidence"}, before[0])

    def test_annotating_twice_gives_the_same_catalog(self):
        records, file = self.sample()
        once = catalog_evidence.annotate(records, file)
        self.assertEqual(catalog_evidence.annotate(once, file), once)

    def test_variants_that_fared_differently_leave_the_catalog_record_studied(self):
        records, file = self.sample()
        file["findings"][0]["exercises"][1]["catalogIDs"] = ["A"]
        annotated = catalog_evidence.annotate(records, file)
        self.assertEqual([entry["result"] for entry in annotated[0]["evidence"]], ["studied"])

    def test_a_single_study_cannot_be_graded_above_low(self):
        records, file = self.sample()
        file["findings"][0]["certainty"] = "moderate"
        problems = catalog_evidence.evidence_problems(file, records)
        self.assertTrue(any("supports at most low certainty" in problem for problem in problems), problems)
        file["sources"]["S1"]["design"] = "metaAnalysis"
        self.assertEqual(catalog_evidence.evidence_problems(file, records), [])

    def test_uncited_or_unknown_values_are_rejected(self):
        records, file = self.sample()
        finding = file["findings"][0]
        finding["source"] = "NOPE"
        finding["outcome"] = "vibes"
        finding["muscles"] = ["pecs"]
        finding["certainty"] = "certain"
        finding["locator"] = ""
        finding["exercises"][0]["catalogIDs"] = ["missing"]
        finding["exercises"][0]["result"] = "best"
        problems = "\n".join(catalog_evidence.evidence_problems(file, records))
        for expected in (
            "unknown source",
            "outcome",
            "unknown muscle",
            "certainty",
            "say where",
            "unknown catalog id",
            "result",
        ):
            self.assertIn(expected, problems)

    def test_internet_content_is_never_a_source(self):
        records, file = self.sample()
        file["sources"]["S1"] = {"citation": "Best chest exercises (video).", "design": "video", "fullTextRead": True}
        problems = "\n".join(catalog_evidence.evidence_problems(file, records))
        self.assertIn("needs a doi or a pmid", problems)
        self.assertIn("design must be one of", problems)

    def test_numbers_read_from_a_preprint_are_rejected(self):
        records, file = self.sample()
        file["findings"][0]["locator"] = "Results of the SportRxiv preprint; published abstract agrees"
        problems = catalog_evidence.evidence_problems(file, records)
        self.assertTrue(any("not a preprint" in problem for problem in problems), problems)

    def test_a_long_paraphrase_is_rejected(self):
        records, file = self.sample()
        file["findings"][0]["finding"] = "word " * (catalog_evidence.MAXIMUM_FINDING_WORDS + 1)
        self.assertTrue(catalog_evidence.evidence_problems(file, records))


class ProgressionIsolationTests(unittest.TestCase):
    def test_load_progression_never_reads_the_catalog(self):
        """AGENTS.md rule 4: load progression reads only logged sets, never catalog annotations."""
        for path in (CORE_DIR / "rules").rglob("*.py"):
            text = path.read_text()
            self.assertNotIn("catalog_evidence", text, path.relative_to(ROOT).as_posix())
            self.assertNotIn("exercises.json", text, path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    unittest.main()
