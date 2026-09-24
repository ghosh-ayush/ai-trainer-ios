"""Weekly plan candidates and their ranking (ADR-017).

The guardrails and structures below are test data shaped like the content bundle's ``weekly``,
``structures`` and ``ranking`` blocks. They mirror the draft research values
(docs/research/training-frequency-evidence.md) but are not the shipped numbers: those come
from the bundle, cited.
"""

import unittest
from itertools import pairwise

from ai_trainer.errors import DomainError
from ai_trainer.rules.plan_ranking import rank_weeks
from ai_trainer.rules.week_plans import week_candidates

WEEKLY = {
    "weeklySetsFloor": 10,
    "weeklySetsCeiling": 20,
    "timeLimitedFloor": 4,
    "sessionSetsCap": 10,
    "consecutiveDayCap": 3,
    "setsPerExerciseMin": 2,
    "setsPerExerciseMax": 5,
    "minutesPerSet": 2.0,
    "warmUpMinutes": 4,
    "maxSessionsPerWeek": 6,
    "strengthExposuresMin": 2,
}

STRUCTURES = {
    "majorMuscles": ["chest", "back", "shoulders", "quadriceps", "hamstrings", "glutes"],
    "roles": {
        "UPH": {"muscles": {"chest": 1, "triceps": 0.5, "shoulders": 0.5}},
        "UPV": {"muscles": {"shoulders": 1, "triceps": 0.5}},
        "ULH": {"muscles": {"back": 1, "biceps": 0.5}},
        "ULV": {"muscles": {"back": 1, "biceps": 0.5}},
        "KD": {"muscles": {"quadriceps": 1, "glutes": 0.5}},
        "HH": {"muscles": {"hamstrings": 1, "glutes": 1}},
        "SL": {"muscles": {"quadriceps": 1, "glutes": 0.5}},
        "EF": {"muscles": {"biceps": 1}},
        "EE": {"muscles": {"triceps": 1}},
        "KF": {"muscles": {"hamstrings": 1}},
        "CALF": {"muscles": {"calves": 1}},
    },
    "sessions": {
        "fullBodyA": {"roles": ["KD", "HH", "UPH", "ULH"], "optional": ["EE", "EF", "CALF"]},
        "fullBodyB": {"roles": ["SL", "HH", "UPV", "ULV"], "optional": ["EF", "EE", "KF"]},
        "fullBodyComplete": {"roles": ["KD", "HH", "UPH", "UPV", "ULH", "ULV"], "optional": ["EF", "EE"]},
        "upper": {"roles": ["UPH", "ULH", "UPV", "ULV"], "optional": ["EF", "EE"]},
        "lower": {"roles": ["KD", "HH", "SL"], "optional": ["KF", "CALF"]},
        "push": {"roles": ["UPH", "UPV"], "optional": ["EE"]},
        "pull": {"roles": ["ULH", "ULV"], "optional": ["EF"]},
        "legs": {"roles": ["KD", "HH", "SL"], "optional": ["KF", "CALF"]},
    },
    "splits": {
        "fullBody": ["fullBodyA", "fullBodyB"],
        "fullBodyComplete": ["fullBodyComplete"],
        "upperLower": ["upper", "lower"],
        "upperLowerFull": ["upper", "lower", "fullBodyA"],
        "pushPullLegs": ["push", "pull", "legs"],
        "pushPullLegsUpperLower": ["push", "pull", "legs", "upper", "lower"],
    },
}

RANKING = {
    "weights": {
        "Hypertrophy": {
            "volume": 4,
            "exposures": 1,
            "recovery": 2,
            "spread": 2,
            "variety": 2,
            "adherence": 2,
            "preference": 1,
        },
        "Strength": {
            "volume": 3,
            "exposures": 3,
            "recovery": 2,
            "spread": 2,
            "variety": 1,
            "adherence": 2,
            "preference": 1,
        },
    },
    "varietyRoles": ["UPH", "UPV", "ULH", "ULV", "HH", "SL"],
    "adherenceSlack": 1,
}

ALL_ROLES = set(STRUCTURES["roles"])
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


def weeks(days, minutes=60, target=10, roles=ALL_ROLES):
    minutes_by_day = minutes if isinstance(minutes, dict) else {day: minutes for day in days}
    return week_candidates(days, minutes_by_day, WEEKLY, STRUCTURES, target, roles)


def muscle_sets(session):
    totals = {}
    for slot in session["slots"]:
        for muscle, credit in STRUCTURES["roles"][slot["role"]]["muscles"].items():
            totals[muscle] = totals.get(muscle, 0.0) + slot["sets"] * credit
    return totals


class GuardrailTests(unittest.TestCase):
    """No candidate may break a guardrail, whatever the free days and minutes."""

    PATTERNS = [
        [SAT],
        [TUE, SAT],
        [MON, WED, FRI],
        [MON, TUE, THU, FRI],
        [MON, TUE, WED, THU, FRI],
        [MON, TUE, WED, THU, FRI, SAT],
        [MON, TUE, WED, THU, FRI, SAT, SUN],
    ]

    def test_every_candidate_keeps_every_guardrail(self):
        for days in self.PATTERNS:
            for minutes in (30, 75):
                for candidate in weeks(days, minutes):
                    with self.subTest(days=days, minutes=minutes, id=candidate["id"]):
                        self.assert_keeps_guardrails(candidate, minutes)

    def assert_keeps_guardrails(self, candidate, minutes):
        self.assertLessEqual(len(candidate["sessions"]), WEEKLY["maxSessionsPerWeek"])
        by_day = {session["day"]: session for session in candidate["sessions"]}
        for session in candidate["sessions"]:
            self.assertLessEqual(session["minutes"], minutes)
            for slot in session["slots"]:
                self.assertGreaterEqual(slot["sets"], WEEKLY["setsPerExerciseMin"])
                self.assertLessEqual(slot["sets"], WEEKLY["setsPerExerciseMax"])
            in_session = muscle_sets(session)
            for muscle, value in in_session.items():
                self.assertLessEqual(value, WEEKLY["sessionSetsCap"])
                day_before = by_day.get((session["day"] - 1) % 7)
                if day_before is not None and day_before is not session and muscle_sets(day_before).get(muscle, 0) > 0:
                    self.assertLessEqual(value, WEEKLY["consecutiveDayCap"], f"{muscle} on consecutive days")
        for value in candidate["weeklySets"].values():
            self.assertLessEqual(value, WEEKLY["weeklySetsCeiling"])
        for muscle in STRUCTURES["majorMuscles"]:
            self.assertGreaterEqual(candidate["weeklySets"].get(muscle, 0), WEEKLY["timeLimitedFloor"])

    def test_seven_free_days_never_schedule_more_than_the_maximum(self):
        candidates = weeks(list(range(7)), 60)
        self.assertTrue(candidates)
        self.assertEqual(max(len(candidate["sessions"]) for candidate in candidates), WEEKLY["maxSessionsPerWeek"])

    def test_candidates_use_only_free_days(self):
        for candidate in weeks([TUE, THU, SAT], 60):
            self.assertTrue(set(candidate["days"]) <= {TUE, THU, SAT})

    def test_a_single_free_day_gives_a_reduced_one_session_week(self):
        candidates = weeks([SAT], 60)
        self.assertTrue(candidates)
        self.assertTrue(all(len(candidate["sessions"]) == 1 for candidate in candidates))
        self.assertEqual({candidate["volume"] for candidate in candidates}, {"reduced"})

    def test_three_spread_days_reach_the_full_weekly_floor(self):
        self.assertIn("full", {candidate["volume"] for candidate in weeks([MON, WED, FRI], 60)})

    def test_too_little_time_gives_no_week(self):
        self.assertEqual(weeks([MON, WED, FRI], 10), [])

    def test_minutes_are_per_day(self):
        candidates = weeks([MON, THU], {MON: 20, THU: 90})
        for candidate in candidates:
            for session in candidate["sessions"]:
                self.assertLessEqual(session["minutes"], 20 if session["day"] == MON else 90)

    def test_unavailable_roles_are_left_out_and_not_required(self):
        roles = ALL_ROLES - {"HH", "KF"}
        candidates = weeks([MON, WED, FRI], 60, roles=roles)
        self.assertTrue(candidates)
        used = {
            slot["role"] for candidate in candidates for session in candidate["sessions"] for slot in session["slots"]
        }
        self.assertNotIn("HH", used)
        self.assertNotIn("KF", used)

    def test_a_missing_role_falls_back_to_its_sibling(self):
        structures = {**STRUCTURES, "fallbacks": {"ULV": "ULH", "UPV": "UPH"}}
        roles = ALL_ROLES - {"ULV"}
        candidates = week_candidates([MON, THU], {MON: 60, THU: 60}, WEEKLY, structures, 10, roles)
        upper = next(
            session
            for candidate in candidates
            if candidate["split"] == "upperLower"
            for session in candidate["sessions"]
            if session["type"] == "upper"
        )
        pulls = [slot["role"] for slot in upper["slots"] if slot["role"] in ("ULH", "ULV")]
        self.assertEqual(pulls, ["ULH"])  # one horizontal pull, not a duplicate and not none

    def test_no_free_day_is_invalid(self):
        with self.assertRaises(DomainError):
            weeks([], 60)

    def test_ids_are_stable_and_readable(self):
        first = [candidate["id"] for candidate in weeks([MON, THU], 60)]
        self.assertEqual(first, [candidate["id"] for candidate in weeks([MON, THU], 60)])
        self.assertIn("upperLower:Mon-upper,Thu-lower", first)


class RankingTests(unittest.TestCase):
    def rank(self, days, minutes=60, **athlete):
        athlete = {"goal": "Hypertrophy", "target": 10, **athlete}
        return rank_weeks(weeks(days, minutes, athlete["target"]), athlete, WEEKLY, STRUCTURES, RANKING)

    def test_best_week_reaches_the_floor_when_time_allows(self):
        best = self.rank([MON, WED, FRI])[0]
        self.assertEqual(best["volume"], "full")
        self.assertIn("REACHES_WEEKLY_FLOOR", best["reasons"])

    def test_strength_prefers_training_each_muscle_at_least_twice(self):
        best = self.rank([MON, TUE, THU, FRI], goal="Strength")[0]
        self.assertEqual(best["features"]["exposures"], 1.0)

    def test_recent_routine_pulls_the_week_towards_fewer_sessions(self):
        free = [MON, TUE, WED, THU, FRI, SAT]
        unknown = self.rank(free)[0]
        busy = self.rank(free, recentSessionsPerWeek=2)[0]
        self.assertEqual(unknown["features"]["adherence"], 0.5)  # no history is neutral, never assumed
        self.assertLessEqual(len(busy["sessions"]), 3)

    def test_a_liked_split_moves_up_but_never_past_a_clearly_better_week(self):
        def position(ranked):
            return next(index for index, item in enumerate(ranked) if item["split"] == "upperLower")

        neutral = self.rank([MON, THU])
        liked = self.rank([MON, THU], likedSplits=["upperLower"])
        self.assertLess(position(liked), position(neutral))
        self.assertIn("A_SPLIT_YOU_LIKE", liked[position(liked)]["reasons"])
        # Upper/lower on two days trains each muscle once; a stated liking does not outrank the evidence.
        self.assertNotEqual(liked[0]["split"], "upperLower")

    def test_sessions_spread_across_the_week_beat_bunched_ones(self):
        best = self.rank(list(range(7)))[0]
        days = best["days"]
        gaps = [later - earlier for earlier, later in pairwise(days)] + [days[0] + 7 - days[-1]]
        self.assertLessEqual(max(gaps), 3, days)  # not four sessions bunched into Fri-Mon

    def test_ranking_is_deterministic(self):
        first = [item["id"] for item in self.rank([MON, WED, FRI, SAT])]
        self.assertEqual(first, [item["id"] for item in self.rank([MON, WED, FRI, SAT])])


if __name__ == "__main__":
    unittest.main()
