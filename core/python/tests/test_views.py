"""Read-only view models: Today's slot cards, the Progress summary and generated load lists."""

import copy
import unittest

from support import NOW, Athlete, call, exposure, result


def views(athlete):
    return result("views", {"state": athlete.state, "permitsFixtures": True, "now": NOW})


def today(athlete):
    return views(athlete)["today"]


def progress(athlete):
    return views(athlete)["progress"]


class TodayStatusTests(unittest.TestCase):
    def test_proposable_slot_is_auto_requested_then_shown_as_a_proposal(self):
        athlete = Athlete.qualified()
        before = copy.deepcopy(athlete.state)
        status = today(athlete)
        self.assertEqual(status["autoRequest"], athlete.slot["id"])
        self.assertEqual(athlete.state, before)  # a query never mutates
        athlete.propose()
        status = today(athlete)
        self.assertIsNone(status["autoRequest"])
        self.assertEqual(status["slots"], [])
        self.assertEqual(status["proposals"][0]["title"], "Proposed · 100 → 105 lb")

    def test_rejected_proposal_is_not_re_proposed_in_the_same_context(self):
        athlete = Athlete.qualified()
        recommendation = athlete.propose()
        athlete.run("rejectRecommendation", id=recommendation["id"], reason="prefer_current")
        status = today(athlete)
        self.assertIsNone(status["autoRequest"])
        self.assertEqual(status["slots"][0]["title"], "Keeping the current plan")

    def test_exposure_progress_counts_the_qualifying_streak(self):
        athlete = Athlete.qualified()
        template = athlete.state["sessions"][0]
        athlete.state["sessions"] = [exposure(template, 100, 1, [10, 10, 10])]
        card = today(athlete)["slots"][0]
        self.assertEqual(card["title"], "1 of 2 comparable sessions done")
        self.assertIn("one more full session", card["body"])

    def test_needs_states_name_their_action(self):
        unknown = Athlete.fresh()
        unknown.slot.pop("load")
        self.assertEqual(today(unknown)["slots"][0]["action"], "setLoad")
        pain = Athlete.qualified()
        pain.state["painExclusions"] = ["bench"]
        card = today(pain)["slots"][0]
        self.assertEqual((card["tone"], card["action"]), ("danger", "swap"))

    def test_active_session_hides_slot_cards(self):
        athlete = Athlete.qualified()
        athlete.start()
        status = today(athlete)
        self.assertEqual((status["slots"], status["autoRequest"]), ([], None))


class ProgressTests(unittest.TestCase):
    def test_recorded_values_newest_first(self):
        block = progress(Athlete.qualified())[0]
        self.assertEqual((block["name"], block["load"], block["unchangedSessions"]), ("Barbell bench press", 100, 2))
        self.assertEqual(block["entries"][0]["summary"], "100 lb × 10 / 10 / 10 · RIR 2")
        self.assertGreater(block["entries"][0]["date"], block["entries"][1]["date"])

    def test_unknowns_are_written_out(self):
        athlete = Athlete.qualified()
        template = athlete.state["sessions"][0]
        session = exposure(template, 100, 1, [8, 8], rir=None)
        for log in session["logs"]:
            log.pop("load")
        session["status"] = "endedEarly"
        athlete.state["sessions"] = [session]
        entry = progress(athlete)[0]
        self.assertEqual(entry["entries"][0]["summary"], "load unknown × 8 / 8 · RIR unknown · ended early")
        self.assertNotIn("load", entry)

    def test_partly_known_effort_says_so(self):
        athlete = Athlete.qualified()
        athlete.state["sessions"][-1]["logs"][0].pop("rir")
        summary = progress(athlete)[0]["entries"][0]["summary"]
        self.assertTrue(summary.endswith("· RIR 2 (some unknown)"), summary)

    def test_no_history_means_no_block(self):
        self.assertEqual(progress(Athlete.fresh()), [])


class LoadStepTests(unittest.TestCase):
    def test_generated_around_the_confirmed_load(self):
        steps = result("loadSteps", {"base": 20, "step": 2.5})
        self.assertEqual((steps[0], steps[-1], len(steps)), (0, 45, 19))
        self.assertIn(22.5, steps)

    def test_step_must_be_positive(self):
        self.assertIn("error", call("loadSteps", {"base": 20, "step": 0}))


if __name__ == "__main__":
    unittest.main()


class PlateLoadTests(unittest.TestCase):
    """ADR-021: plates per side from the athlete's own bar and plates."""

    def plates(self, load, bar=20, plates=(25, 20, 15, 10, 5, 2.5, 1.25)):
        return result("plateLoad", {"load": load, "bar": bar, "plates": list(plates)})

    def test_largest_plates_first_for_an_exact_load(self):
        self.assertEqual(self.plates(102.5), {"perSide": [25, 15, 1.25], "total": 102.5, "exact": True})

    def test_a_load_that_cannot_be_made_gives_the_nearest_lower_total(self):
        answer = self.plates(101)
        self.assertEqual((answer["total"], answer["exact"]), (100, False))

    def test_the_bar_alone_and_a_load_below_it(self):
        self.assertEqual(self.plates(20)["perSide"], [])
        self.assertEqual((self.plates(15)["total"], self.plates(15)["exact"]), (20, False))

    def test_pounds_work_the_same_way(self):
        self.assertEqual(self.plates(225, bar=45, plates=(45, 25, 10, 5, 2.5))["perSide"], [45, 45])

    def test_no_plates_or_a_negative_bar_is_invalid(self):
        self.assertEqual(call("plateLoad", {"load": 100, "bar": 20, "plates": []})["error"]["code"], "invalid")
        self.assertEqual(call("plateLoad", {"load": 100, "bar": -1, "plates": [5]})["error"]["code"], "invalid")
