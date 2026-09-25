"""The model's rewording of a chat answer (ADR-027): shown only when it adds no number or exercise.

These wordings stand in for what Apple's on-device model returns. The check never edits a wording;
it accepts it or refuses it, and a refused wording means the app's facts are shown instead.
"""

import unittest

from support import NOW, Athlete, call, result

from ai_trainer import contracts

BENCH = "Barbell bench press"


def bench_reply():
    payload = {
        "state": Athlete.qualified().state,
        "text": "why is my bench not going up?",
        "draft": {"topic": "exerciseProgress", "exercise": BENCH},
        "permitsFixtures": True,
        "now": NOW,
    }
    return result("chat", payload)


def check(reply, wording, message="why is my bench not going up?", earlier=None):
    payload = {"reply": reply, "wording": wording, "message": message, "permitsFixtures": True}
    if earlier is not None:
        payload["earlier"] = earlier
    return result("checkChatWording", payload)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.reply = bench_reply()

    def test_a_faithful_rewording_is_shown(self):
        wording = (
            f"Good news: your {BENCH} is ready to move up. Your last two sessions were 100 lb for 10, 10 and 10 "
            "reps with 2 in reserve, so the next available load is ready to review."
        )
        checked = check(self.reply, wording)
        self.assertEqual(checked, {"text": wording, "accepted": True, "dropped": []})

    def test_a_number_the_facts_do_not_have_is_refused(self):
        checked = check(self.reply, "You should add 15 lb next time.")
        self.assertEqual((checked["accepted"], checked["dropped"], checked["text"]), (False, ["15"], ""))

    def test_numbers_written_as_words_are_checked_too(self):
        self.assertEqual(check(self.reply, "Do fifteen reps next time.")["dropped"], ["15"])
        self.assertTrue(check(self.reply, "You did ten reps on every set.")["accepted"])

    def test_an_exercise_the_facts_do_not_name_is_refused(self):
        checked = check(self.reply, "Try the Goblet squat instead.")
        self.assertFalse(checked["accepted"])
        self.assertEqual(checked["dropped"], ["Goblet squat"])

    def test_the_athletes_own_numbers_may_be_used(self):
        self.assertTrue(check(self.reply, "You asked about 3 sessions.", message="what about 3 sessions?")["accepted"])
        self.assertTrue(check(self.reply, "About those 7 days.", earlier="I have 7 days")["accepted"])

    def test_pain_answers_are_never_reworded(self):
        pain = dict(self.reply, topic="pain")
        checked = check(pain, "Take it easy.")
        self.assertEqual((checked["accepted"], checked["dropped"]), (False, ["pain answers keep the app's wording"]))

    def test_empty_long_or_linked_wording_is_refused(self):
        self.assertFalse(check(self.reply, "   ")["accepted"])
        self.assertFalse(check(self.reply, "word " * 300)["accepted"])
        self.assertFalse(check(self.reply, "See https://example.com")["accepted"])

    def test_the_answer_matches_the_contract(self):
        payload = {"reply": self.reply, "wording": "Ready to move up.", "message": "hi", "permitsFixtures": True}
        contracts.validate(call("checkChatWording", payload), contracts.RESPONSE, contracts.RESPONSE)


if __name__ == "__main__":
    unittest.main()
