"""Chat with the app (ADR-023): the model reads a message, the core writes every answer.

The draft is what the on-device model read. These tests hand the core drafts the way the model
really returns them (with numbers and exercises the athlete never said) and check that only
what the athlete said survives, that answers come from records and cited content, and that
nothing changes until a tapped action runs.
"""

import copy
import unittest

from support import NOW, Athlete, call, progression, result

from ai_trainer import content, contracts
from ai_trainer.chat import chat_reply
from ai_trainer.rules.eligibility import decide
from ai_trainer.rules.program import initial_program

DAY = 86400.0
BENCH = "Barbell bench press"


def ask(athlete, text, utc_offset=0, **draft):
    """One chat message through the real JSON entry point."""
    draft.setdefault("topic", "other")
    payload = {
        "state": athlete.state,
        "text": text,
        "draft": draft,
        "permitsFixtures": True,
        "now": NOW,
        "utcOffset": utc_offset,
    }
    return result("chat", payload)


def kinds(reply):
    return [action["kind"] for action in reply["actions"]]


def action(reply, kind):
    return next(item for item in reply["actions"] if item["kind"] == kind)


def evidence_athlete():
    """An athlete on a real evidence-2 week, with that bundle's library and raw citations."""
    manifest, raw = content.all_bundles()["evidence-2"]
    body = content._resolved(raw)
    library = {key: body[key] for key in ("exercises", "policy", "template", "planner")}
    library["permitsFixtures"] = False
    state = Athlete.fresh().state
    profile = copy.deepcopy(state["profile"])
    profile.update(
        goal="Hypertrophy", experience="Beginner", preferredUnit="kg", equipment=["dumbbell"], freeDays=[0, 2, 4]
    )
    state["profile"] = profile
    ids = [f"00000000-0000-0000-0000-{number:012d}" for number in range(100, 180)]
    state["program"] = initial_program(profile, library, NOW, ids)
    return state, library, (manifest, raw)


def ask_real(state, library, bundle, text, **draft):
    return chat_reply(state, text, draft, library, bundle, NOW, None, 0)


class GroundingTests(unittest.TestCase):
    """Only what the athlete said survives the model's draft (the ADR-015 rule, for chat)."""

    def test_numbers_the_athlete_never_said_are_dropped(self):
        reply = ask(Athlete.qualified(), "why is my bench not going up?", topic="exerciseProgress", minutes=15, days=3)
        self.assertEqual(reply["ignored"], ["minutes", "days"])

    def test_minutes_count_when_said_in_digits_hours_or_half_an_hour(self):
        athlete = Athlete.qualified()
        self.assertEqual(
            ask(athlete, "I have 30 minutes", topic="lessTime", minutes=30)["reading"], "Less time: 30 minutes"
        )
        self.assertEqual(
            ask(athlete, "only 2 hours", topic="lessTime", minutes=120)["reading"], "Less time: 120 minutes"
        )
        self.assertEqual(ask(athlete, "half an hour", topic="lessTime", minutes=30)["reading"], "Less time: 30 minutes")

    def test_half_an_hour_is_not_an_hour(self):
        reply = ask(Athlete.qualified(), "I only have half an hour", topic="lessTime", minutes=60)
        self.assertEqual(reply["ignored"], ["minutes"])
        self.assertEqual(kinds(reply), ["openLessTime"])

    def test_days_count_when_said_as_days_or_weeks_but_not_from_a_stray_a(self):
        athlete = Athlete.qualified()
        self.assertEqual(ask(athlete, "on holiday for 2 weeks", topic="away", days=14)["ignored"], [])
        self.assertEqual(ask(athlete, "sick for a week", topic="away", days=7)["ignored"], [])
        self.assertEqual(ask(athlete, "away a few days this week", topic="away", days=7)["ignored"], ["days"])

    def test_an_exercise_the_athlete_did_not_name_is_dropped(self):
        reply = ask(Athlete.qualified(), "how much protein do I have left", topic="diet", exercise=BENCH)
        self.assertEqual(reply["ignored"], ["exercise"])

    def test_a_word_of_the_name_is_enough(self):
        reply = ask(Athlete.qualified(), "how is bench going", topic="exerciseProgress")
        self.assertEqual(reply["reading"], f"How {BENCH} is going")

    def test_a_shared_word_asks_which_exercise(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(state, library, bundle, "how is my press going", topic="exerciseProgress")
        self.assertEqual(reply["reading"], "Which exercise?")
        presses = [item["draft"]["exercise"] for item in reply["actions"]]
        self.assertEqual(len(presses), 2)
        self.assertTrue(all("press" in name.lower() for name in presses))
        self.assertTrue(all(item["kind"] == "ask" for item in reply["actions"]))

    def test_the_models_pick_wins_among_the_exercises_the_athlete_named(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(
            state,
            library,
            bundle,
            "how is my floor press going",
            topic="exerciseProgress",
            exercise="Dumbbell floor press",
        )
        self.assertEqual(reply["reading"], "How Dumbbell floor press is going")

    def test_long_messages_are_refused(self):
        response = call(
            "chat",
            {
                "state": Athlete.qualified().state,
                "text": "x" * 501,
                "draft": {"topic": "other"},
                "permitsFixtures": True,
                "now": NOW,
            },
        )
        self.assertEqual(response["error"]["code"], "invalid")


class SafetyTests(unittest.TestCase):
    def test_pain_words_get_the_pain_answer_whatever_the_model_chose(self):
        reply = ask(Athlete.qualified(), "I'm sick and my knee hurts", topic="away")
        self.assertEqual(reply["topic"], "pain")
        self.assertIn("The app can't assess pain or tell which exercises are safe with it.", reply["lines"])
        self.assertEqual(kinds(reply), ["openPain", "setStatus", "setStatus"])
        self.assertEqual([item.get("status") for item in reply["actions"][1:]], ["sick", "injured"])

    def test_naming_the_exercise_offers_to_pause_it(self):
        reply = ask(Athlete.qualified(), "my shoulder hurts on bench", topic="pain", exercise=BENCH)
        pause = action(reply, "reportPain")
        self.assertEqual(pause["exerciseID"], Athlete.qualified().slot["exerciseID"])

    def test_talk_of_days_offers_to_change_the_free_days(self):
        reply = ask(Athlete.qualified(), "I want to train on weekends instead", topic="changePlan")
        self.assertIn("openChangeDays", kinds(reply))

    def test_a_week_with_several_sessions_offers_a_different_one_today(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(state, library, bundle, "I want to do legs today instead", topic="changePlan")
        self.assertIn("openSwapSession", kinds(reply))
        single = ask(Athlete.qualified(), "can I do something else today", topic="changePlan")
        self.assertNotIn("openSwapSession", kinds(single), "one session has nothing to swap with")

    def test_a_lighter_week_is_not_invented(self):
        reply = ask(Athlete.qualified(), "my knee hurts, lighter legs this week", topic="pain")
        self.assertTrue(any("no cited rule for a lighter week" in line for line in reply["lines"]))


class AnswersFromRecordsTests(unittest.TestCase):
    def test_progress_uses_the_decision_a_proposal_would_use(self):
        athlete = Athlete.qualified()
        reply = ask(athlete, "why is my bench not going up?", topic="exerciseProgress", exercise=BENCH)
        expected = athlete.decide(progression(athlete.slot["id"]))["explanation"]
        self.assertIn(expected, reply["lines"])
        self.assertTrue(reply["lines"][0].startswith("Last time: "))
        self.assertIn("100 lb × 10 / 10 / 10 · RIR 2", reply["lines"][0])
        self.assertEqual(action(reply, "requestProgression")["slotID"], athlete.slot["id"])

    def test_no_load_yet_offers_the_load_sheet(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(state, library, bundle, "why is my squat not going up", topic="exerciseProgress")
        self.assertIn("Confirm a familiar working load. The app does not estimate your strength.", reply["lines"])
        self.assertEqual(kinds(reply), ["openLoad"])

    def test_less_time_previews_only_what_the_decision_proposes(self):
        state, library, bundle = evidence_athlete()
        plan = state["program"]["plans"][0]
        minutes = 30
        decision = decide(state, {"kind": "shorten", "minutes": minutes}, library, NOW)
        reply = ask_real(state, library, bundle, f"only {minutes} minutes", topic="lessTime", minutes=minutes)
        self.assertEqual(reply["lines"][0], f"With {minutes} minutes: {decision['explanation']}")
        if decision["outcome"] == "proposeChange":
            self.assertEqual(action(reply, "requestShorten")["minutes"], minutes)
        else:
            self.assertNotIn("requestShorten", kinds(reply))
        self.assertTrue(plan["slots"])

    def test_the_week_lists_its_days_and_this_weeks_sets(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(state, library, bundle, "which days do I train", topic="week")
        self.assertTrue(reply["lines"][0].startswith("Your week: Mon "))
        self.assertIn("Wed ", reply["lines"][0])
        self.assertIn("Fri ", reply["lines"][0])
        self.assertTrue(reply["lines"][1].startswith("Sets logged this week against the weekly target: chest 0 of 10"))
        self.assertEqual(kinds(reply), ["requestReplan", "openToday"])

    def test_the_next_session_lists_each_prescription(self):
        reply = ask(Athlete.qualified(), "what's my workout today", topic="nextSession")
        self.assertIn(f"{BENCH}: 3 × 8 / 8 / 8 reps at 100 lb", reply["lines"])


class StatusTests(unittest.TestCase):
    def test_a_said_length_becomes_the_end_of_the_break(self):
        reply = ask(Athlete.qualified(), "going on holiday for 10 days", topic="away", days=10)
        mark = action(reply, "setStatus")
        self.assertEqual((mark["status"], mark["endsAt"]), ("onBreak", NOW + 10 * DAY))
        self.assertEqual(mark["title"], "Mark me on a break for 10 days")

    def test_no_kind_offers_all_three(self):
        reply = ask(Athlete.qualified(), "I need some time off", topic="away")
        statuses = [item.get("status") for item in reply["actions"] if item["kind"] == "setStatus"]
        self.assertEqual(statuses, ["onBreak", "sick", "injured"])

    def test_naming_two_kinds_is_not_a_choice(self):
        reply = ask(Athlete.qualified(), "I'm sick or away", topic="away")
        statuses = [item.get("status") for item in reply["actions"] if item["kind"] == "setStatus"]
        self.assertEqual(statuses, ["onBreak", "sick", "injured"])

    def test_while_marked_away_the_answer_is_the_current_status(self):
        athlete = Athlete.qualified()
        athlete.run("setStatus", status="injured")
        reply = ask(athlete, "I'm sick or away", topic="away")
        self.assertEqual(reply["lines"], ["You are marked injured. Tap I'm back to resume the app's suggestions."])
        self.assertEqual(kinds(reply), ["endStatus"])

    def test_no_length_means_until_back(self):
        reply = ask(Athlete.qualified(), "I have the flu", topic="away")
        self.assertEqual(action(reply, "setStatus")["title"], "Mark me sick until I'm back")
        self.assertNotIn("endsAt", action(reply, "setStatus"))

    def test_back_ends_the_current_status(self):
        athlete = Athlete.qualified()
        athlete.run("setStatus", status="sick", endsAt=NOW + 3 * DAY)
        reply = ask(athlete, "I'm back", topic="away")
        self.assertEqual(kinds(reply), ["endStatus"])


class EvidenceTests(unittest.TestCase):
    def test_test_content_says_it_has_no_research_behind_it(self):
        reply = ask(Athlete.qualified(), "where do these numbers come from", topic="evidence")
        self.assertEqual(reply["sources"], [])
        self.assertIn("no research behind them", reply["lines"][0])

    def test_a_question_about_rest_cites_the_rest_source(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(state, library, bundle, "why do I rest 90 seconds", topic="evidence")
        manifest, raw = bundle
        cited = raw["template"]["slotByGoal"]["Hypertrophy"]["restSeconds"]
        self.assertEqual(len(reply["lines"]), 1)
        self.assertTrue(reply["lines"][0].startswith(f"Rest, {cited['value']} seconds between sets: From "))
        self.assertIn(cited["note"], reply["lines"][0])
        keys = [source["key"] for source in reply["sources"]]
        self.assertEqual(keys[0], cited["source"])  # the value's own source first
        self.assertIn("ACSM09", keys)  # then every source its note names ("ACSM09: 1-2 minutes")
        self.assertEqual(reply["sources"][0]["doi"], manifest["sources"][cited["source"]]["doi"])

    def test_the_apps_own_rules_say_so_and_cite_what_they_are_built_from(self):
        state, library, bundle = evidence_athlete()
        reply = ask_real(state, library, bundle, "why this many sets", topic="evidence")
        self.assertIn("No study gives this exact number, so it is the app's own rule.", reply["lines"][0])
        keys = [source["key"] for source in reply["sources"]]
        manifest, _ = bundle
        self.assertTrue(keys)
        self.assertTrue(all(key in manifest["sources"] for key in keys))


class NothingChangesTests(unittest.TestCase):
    def test_chat_is_read_only(self):
        athlete = Athlete.qualified()
        before = copy.deepcopy(athlete.state)
        for text, topic in (
            ("why is my bench not going up", "exerciseProgress"),
            ("I only have 20 minutes", "lessTime"),
            ("my knee hurts", "pain"),
            ("sick for 3 days", "away"),
            ("make it harder", "changePlan"),
        ):
            ask(athlete, text, topic=topic)
        self.assertEqual(athlete.state, before)

    def test_every_reply_matches_the_contract(self):
        athlete = Athlete.qualified()
        for topic in (
            "exerciseProgress",
            "nextSession",
            "week",
            "lessTime",
            "moveOrSkip",
            "pain",
            "away",
            "changePlan",
            "evidence",
            "diet",
            "other",
        ):
            payload = {
                "state": athlete.state,
                "text": "hello",
                "draft": {"topic": topic},
                "permitsFixtures": True,
                "now": NOW,
            }
            contracts.validate(call("chat", payload), contracts.RESPONSE, contracts.RESPONSE)

    def test_unclear_messages_offer_the_starter_questions(self):
        reply = ask(Athlete.qualified(), "tell me a joke", topic="other")
        self.assertEqual(kinds(reply), ["ask"] * 7)
        self.assertEqual(reply["actions"][0]["draft"], {"topic": "exerciseProgress"})


if __name__ == "__main__":
    unittest.main()
