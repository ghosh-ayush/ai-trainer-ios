"""readSet: a set the athlete described in words becomes a preview, never a saved record.

The draft stands in for what the on-device language model returns. Whatever the draft says,
only numbers the athlete actually said survive, and nothing is written until ``saveSet``.
"""

import copy
import unittest

from support import Athlete, call, result, uid

BENCH = "Barbell bench press"
SQUAT = "Goblet squat"


def read(athlete, text, **draft):
    """One ``readSet`` call against the athlete's current state."""
    payload = {"state": athlete.state, "text": text, "draft": draft, "permitsFixtures": True}
    return result("readSet", payload)


def with_squat_slot(athlete):
    """Adds a goblet squat slot after the bench slot of the next plan."""
    plan = athlete.plan
    squat = copy.deepcopy(plan["slots"][0])
    squat["id"] = uid(900)
    squat["exerciseID"] = "goblet_squat"
    plan["slots"].append(squat)
    return athlete


class ReadSetTests(unittest.TestCase):
    def setUp(self):
        self.athlete = Athlete.fresh()
        self.session = self.athlete.start()

    def test_said_numbers_become_a_preview_and_nothing_is_saved(self):
        before = copy.deepcopy(self.athlete.state)
        reading = read(self.athlete, "bench 100 for 8, 2 left", exercise=BENCH, reps=8, load=100, rir=2)
        self.assertEqual(self.athlete.state, before)  # a query never mutates
        self.assertEqual(reading["ignored"], [])
        preview = reading["preview"]
        self.assertEqual(preview["name"], BENCH)
        self.assertEqual(preview["slotID"], self.session["plan"]["slots"][0]["id"])
        self.assertEqual((preview["reps"], preview["load"], preview["rir"]), (8, 100, 2))
        self.assertEqual((preview["kind"], preview["index"], preview["unit"]), ("working", 0, "lb"))

    def test_a_confirmed_preview_saves_through_the_normal_command(self):
        preview = read(self.athlete, "8 at 100", reps=8, load=100)["preview"]
        self.athlete.run(
            "saveSet",
            sessionID=preview["sessionID"],
            slotID=preview["slotID"],
            index=preview["index"],
            kind=preview["kind"],
            reps=preview["reps"],
            load=preview["load"],
            logID=uid(7000),
            operationID=uid(7001),
        )
        log = self.athlete.active_session["logs"][0]
        self.assertEqual((log["reps"], log["load"]), (8, 100))
        self.assertNotIn("rir", log)  # never said, so never recorded

    def test_numbers_the_athlete_never_said_are_dropped(self):
        reading = read(self.athlete, "bench for 8", exercise=BENCH, reps=8, load=100, rir=2)
        preview = reading["preview"]
        self.assertEqual(preview["reps"], 8)
        self.assertNotIn("load", preview)
        self.assertNotIn("rir", preview)
        self.assertEqual(reading["ignored"], ["load", "rir"])

    def test_one_spoken_number_backs_one_field(self):
        # What the on-device model returned for these words on 2026-09-23.
        reading = read(self.athlete, "felt heavy, maybe 6", reps=6, load=6)
        self.assertEqual(reading["preview"]["reps"], 6)
        self.assertNotIn("load", reading["preview"])
        self.assertEqual(reading["ignored"], ["load"])
        both = read(self.athlete, "6 at 6", reps=6, load=6)["preview"]
        self.assertEqual((both["reps"], both["load"]), (6, 6))

    def test_number_words_count_as_said(self):
        preview = read(self.athlete, "eight reps at 100, two in reserve", reps=8, load=100, rir=2)["preview"]
        self.assertEqual((preview["reps"], preview["load"], preview["rir"]), (8, 100, 2))

    def test_decimal_loads_are_matched_exactly(self):
        preview = read(self.athlete, "8 reps with 102.5", reps=8, load=102.5)["preview"]
        self.assertEqual(preview["load"], 102.5)
        reading = read(self.athlete, "8 reps with 102", reps=8, load=102.5)
        self.assertEqual(reading["ignored"], ["load"])

    def test_missing_reps_is_a_question(self):
        reading = read(self.athlete, "bench 100", exercise=BENCH, reps=10, load=100)
        self.assertNotIn("preview", reading)
        self.assertEqual(reading["question"], f"How many reps did you do on {BENCH}?")
        self.assertEqual(reading["ignored"], ["reps"])

    def test_out_of_range_rir_is_dropped(self):
        reading = read(self.athlete, "12 reps at 100", reps=12, load=100, rir=12)
        self.assertNotIn("rir", reading["preview"])
        self.assertEqual(reading["ignored"], ["rir"])

    def test_another_unit_is_a_question_not_a_conversion(self):
        reading = read(self.athlete, "bench 45 kg for 8", exercise=BENCH, reps=8, load=45)
        self.assertEqual(reading["question"], f"{BENCH} is recorded in lb. Say the load in lb.")
        preview = read(self.athlete, "bench 100 lbs for 8", reps=8, load=100)["preview"]
        self.assertEqual(preview["unit"], "lb")

    def test_warm_up_and_extra_sets_only_when_said(self):
        warm_up = read(self.athlete, "warm-up 5 at 45", reps=5, load=45)["preview"]
        self.assertEqual((warm_up["kind"], warm_up["index"]), ("warmUp", 0))
        extra = read(self.athlete, "extra set of 10 at 80", reps=10, load=80)["preview"]
        self.assertEqual(extra["kind"], "extra")

    def test_working_sets_fill_in_order_then_ask_for_an_extra_set(self):
        for index in range(3):
            preview = read(self.athlete, "8 at 100", reps=8, load=100)["preview"]
            self.assertEqual(preview["index"], index)
            self.athlete.save_set(self.athlete.active_session, index, reps=8, load=100)
        reading = read(self.athlete, "8 at 100", reps=8, load=100)
        self.assertEqual(reading["question"], f'All 3 working sets of {BENCH} are logged. Say "extra set" to add one.')

    def test_paused_session_asks_to_resume(self):
        self.athlete.run("setPaused", paused=True)
        self.assertEqual(read(self.athlete, "8 at 100", reps=8)["question"], "Resume the session to log sets.")


class ExerciseResolutionTests(unittest.TestCase):
    def setUp(self):
        self.athlete = with_squat_slot(Athlete.fresh())
        self.session = self.athlete.start()

    def test_the_exercise_the_athlete_named_wins_over_the_models_pick(self):
        reading = read(self.athlete, "squats, 8 at 40", exercise=BENCH, reps=8, load=40)
        self.assertEqual(reading["preview"]["name"], SQUAT)
        self.assertEqual(reading["ignored"], ["exercise"])

    def test_no_exercise_named_means_the_next_open_set(self):
        self.assertEqual(read(self.athlete, "8 at 100", reps=8, load=100)["preview"]["name"], BENCH)
        for index in range(3):
            self.athlete.save_set(self.athlete.active_session, index, reps=8, load=100)
        self.assertEqual(read(self.athlete, "8 at 40", reps=8, load=40)["preview"]["name"], SQUAT)

    def test_an_exercise_outside_the_session_is_a_question_not_the_next_set(self):
        # The model returned no exercise for these words, so the set would have gone to the next slot.
        reading = read(self.athlete, "curls 12 at 30", reps=12, load=30)
        self.assertEqual(reading["question"], f"That exercise isn't in today's session. Today: {BENCH}, {SQUAT}.")

    def test_two_exercises_named_is_a_question(self):
        reading = read(self.athlete, "bench then squat, 8 each", reps=8)
        self.assertEqual(reading["question"], f"Which exercise was that? Today: {BENCH}, {SQUAT}.")

    def test_the_models_pick_settles_two_exercises_named(self):
        reading = read(self.athlete, "bench then squat, 8 each", exercise=SQUAT, reps=8)
        self.assertEqual(reading["preview"]["name"], SQUAT)


class ReadSetErrorTests(unittest.TestCase):
    def test_no_active_session_is_invalid(self):
        payload = {"state": Athlete.fresh().state, "text": "8 at 100", "draft": {"reps": 8}, "permitsFixtures": True}
        self.assertEqual(call("readSet", payload)["error"]["code"], "invalid")

    def test_empty_or_overlong_text_is_invalid(self):
        athlete = Athlete.fresh()
        athlete.start()
        for text in ("   ", "8 " * 300):
            payload = {"state": athlete.state, "text": text, "draft": {"reps": 8}, "permitsFixtures": True}
            self.assertEqual(call("readSet", payload)["error"]["code"], "invalid")


if __name__ == "__main__":
    unittest.main()
