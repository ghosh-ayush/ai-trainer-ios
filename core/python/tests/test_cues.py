"""Spoken coaching cues (ADR-022): every word from the plan and logged sets, never invented."""

import unittest

from support import NOW, Athlete, result


def cues(athlete, now=NOW):
    return result("workoutCues", {"state": athlete.state, "permitsFixtures": True, "now": now})


class WorkoutCueTests(unittest.TestCase):
    def test_no_workout_no_cues(self):
        self.assertEqual(cues(Athlete.qualified()), {})

    def test_the_first_set_comes_with_what_was_done_last_time(self):
        athlete = Athlete.qualified()
        athlete.start()
        said = cues(athlete)
        self.assertEqual(
            said["next"],
            "Next: Barbell bench press, set 1 of 3: 8 reps at 100 pounds. "
            "Last time you did 10, 10 and 10 reps at 100 pounds.",
        )
        self.assertNotIn("afterSet", said)

    def test_after_a_set_the_rest_and_the_next_set(self):
        athlete = Athlete.qualified()
        athlete.start()
        athlete.save_set(athlete.active_session, 0, reps=10, load=100)
        said = cues(athlete, NOW + 60)
        self.assertEqual(
            said["afterSet"],
            "Set 1 of Barbell bench press done. Rest 2 minutes. "
            "Next: Barbell bench press, set 2 of 3: 8 reps at 100 pounds.",
        )
        self.assertEqual(said["restOver"], "Rest's over. Barbell bench press, set 2 of 3: 8 reps at 100 pounds.")

    def test_after_the_last_planned_set(self):
        athlete = Athlete.qualified()
        athlete.start()
        for index in range(3):
            athlete.save_set(athlete.active_session, index, reps=8, load=100)
        said = cues(athlete, NOW + 300)
        self.assertTrue(said["afterSet"].startswith("Set 3 of Barbell bench press done."), said["afterSet"])
        self.assertTrue(said["afterSet"].endswith("That was the last planned set. Tap Finish when you're done."))
        self.assertNotIn("next", said)

    def test_an_unknown_load_is_said_to_be_unknown(self):
        athlete = Athlete.fresh()
        athlete.state["program"]["plans"][0]["slots"][0].pop("load", None)
        athlete.start()
        self.assertIn("8 reps at a load you choose.", cues(athlete)["next"])


if __name__ == "__main__":
    unittest.main()
