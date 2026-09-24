"""The diet engine: targets, trend, adjustments, safety, food logging and suggestions.

Rules run against ``TEST_POLICY`` — test data, not a prescription (AGENTS.md rule 1) — so the
tests do not change when research updates the shipped diet bundle. ``ShippedDietBundleTests``
checks the real bundle separately.
"""

import copy
import unittest
from unittest import mock

from support import NOW, call, golden_request, result, uid

from ai_trainer import diet, diet_content, diet_view, foods

DAY = 86_400.0

TEST_POLICY = {
    "version": "diet-test",
    "energy": {
        "eerCoefficients": {
            sex: {
                level: {"intercept": 600.0, "age": -10.0, "heightCm": 6.0, "weightKg": 14.0}
                for level in ("inactive", "lowActive", "active", "veryActive")
            }
            for sex in ("female", "male")
        },
        "activityLevels": [
            {"id": "lowActive", "title": "Low active", "description": "Test.", "palMin": 1.5, "palMax": 1.7}
        ],
        "kcalPerGram": {"protein": 4, "carbohydrate": 4, "fat": 9},
        "tissueKcalPerKgBodyMass": 7000,
        "predictionErrorKcal": {"female": 250, "male": 350},
    },
    "goals": {
        "fatLoss": {"weeklyChangeFraction": -0.005, "proteinGPerKgBodyMass": 2.0, "maxWeeklyLossFraction": 0.01},
        "muscleGain": {"weeklyChangeFraction": 0.0025, "proteinGPerKgBodyMass": 1.6, "maxWeeklyGainFraction": 0.005},
        "maintenance": {"weeklyChangeFraction": 0.0, "proteinGPerKgBodyMass": 1.6, "stableBandFractionPerWeek": 0.0025},
        "endurance": {
            "weeklyChangeFraction": 0.0,
            "proteinGPerKgBodyMass": 1.4,
            "carbohydrateGPerKgByTrainingLoad": {
                "light": [3, 5],
                "moderate": [5, 7],
                "high": [6, 10],
                "veryHigh": [8, 12],
            },
        },
    },
    "macros": {
        "fatMinimumEnergyFraction": 0.2,
        "fatMaximumEnergyFraction": 0.35,
        "fatDefaultEnergyFraction": 0.3,
        "carbohydrateMinimumGPerDay": 130,
        "proteinMinimumGPerKgBodyMass": 0.8,
        "proteinMaximumGPerKgBodyMass": 2.2,
        "fibreGPer1000Kcal": 14,
        "proteinReferenceFromBMI": 30,
        "proteinReferenceBMI": 25,
        "proteinMaximumEnergyFraction": 0.35,
        "fibreMinimumG": 25,
        "fibreMaximumG": 40,
    },
    "adaptation": {
        "defaultPace": "slower",
        "paces": {
            "slower": {
                "windowDays": 14,
                "minimumWeighIns": 4,
                "minimumWeighInDaysPerWeek": 2,
                "toleranceFractionPerWeek": 0.002,
                "adjustmentStepKcal": 150,
                "minimumDaysBetweenAdjustments": 14,
            },
            "standard": {
                "windowDays": 7,
                "minimumWeighIns": 3,
                "minimumWeighInDaysPerWeek": 2,
                "toleranceFractionPerWeek": 0.003,
                "adjustmentStepKcal": 100,
                "minimumDaysBetweenAdjustments": 7,
            },
        },
        "paceCopy": {"question": "q", "slower": "s", "standard": "m", "perceivedMetabolismNote": "n"},
        "intakeNote": "Logged intake is shown, not used to recompute targets.",
    },
    "safety": {
        "minimumAgeYears": 18,
        "exclusions": [
            {"id": identifier, "title": identifier, "description": "Test.", "action": "withholdTargets"}
            for identifier in ("pregnancy", "lactation", "eatingDisorderRisk", "chronicKidneyDisease", "type1Diabetes")
        ],
        "scoff": {"questions": ["q1", "q2", "q3", "q4", "q5"], "referralScore": 2},
        "minimumEnergyKcal": {"female": 1200, "male": 1500},
        "energyAvailabilityFloorKcalPerKgFFM": 30,
        "maximumDeficitFractionOfTEE": 0.25,
        "minimumBMI": 17.5,
        "fatLossMinimumBMI": 18.5,
        "rapidLossFraction": 0.10,
        "rapidLossDays": 30,
    },
    "patterns": {"vegetarian": {"proteinMultiplier": 1.0}, "vegan": {"proteinMultiplier": 1.1}},
    "foods": {
        "proteinDenseGPer100Kcal": 8,
        "proteinDenseMinGPer100g": 10,
        "minimumPortionProteinG": 10,
        "minimumPortionFibreG": 3,
    },
}


def profile(**changes):
    base = {
        "sex": "male",
        "birthYear": 1996,
        "heightCm": 180.0,
        "activity": "lowActive",
        "goal": "maintenance",
        "pattern": "omnivore",
        "cuisines": [],
        "screening": {"pregnant": False, "lactating": False, "conditions": [], "scoffAnswers": [False] * 5},
    }
    base.update(changes)
    return base


def weigh_ins(start_kg, weekly_change_kg, days=14, every=2):
    return [
        {
            "id": uid(900 + i),
            "kg": start_kg + weekly_change_kg * (i * every) / 7,
            "measuredAt": NOW - (days - i * every) * DAY,
            "source": "manual",
            "timeZone": "UTC",
            "utcOffsetSeconds": 0,
        }
        for i in range(days // every + 1)
    ]


class PolicyPatch(unittest.TestCase):
    """Runs every test against TEST_POLICY in place of the shipped diet bundle."""

    def setUp(self):
        loaded = {"policy": TEST_POLICY, "sources": {}, "citations": []}
        patcher = mock.patch.object(diet_content, "_active", lambda: loaded)
        patcher.start()
        self.addCleanup(patcher.stop)


class CalendarTests(unittest.TestCase):
    def test_calendar_year_without_datetime(self):
        self.assertEqual(diet.calendar_year(0), 2001)
        self.assertEqual(diet.calendar_year(NOW), 2026)
        self.assertEqual(diet.calendar_year(757_382_399), 2024)  # 2024-12-31T23:59:59Z
        self.assertEqual(diet.calendar_year(757_382_400), 2025)  # 2025-01-01T00:00:00Z


class TargetTests(unittest.TestCase):
    def test_energy_follows_the_published_equation_form(self):
        requirement = diet.estimated_energy_requirement(profile(), 80, NOW, TEST_POLICY)
        self.assertAlmostEqual(requirement, 600 - 10 * 30 + 6 * 180 + 14 * 80)

    def test_goals_shift_energy_and_macros_add_up(self):
        maintenance, _ = diet.targets_for(profile(), 80, NOW, TEST_POLICY, "setup")
        loss, _ = diet.targets_for(profile(goal="fatLoss"), 80, NOW, TEST_POLICY, "setup")
        gain, _ = diet.targets_for(profile(goal="muscleGain"), 80, NOW, TEST_POLICY, "setup")
        self.assertLess(loss["energyKcal"], maintenance["energyKcal"])
        self.assertGreater(gain["energyKcal"], maintenance["energyKcal"])
        self.assertEqual(loss["proteinG"], 160)
        for targets in (maintenance, loss, gain):
            total = targets["proteinG"] * 4 + targets["carbohydrateG"] * 4 + targets["fatG"] * 9
            self.assertLess(abs(total - targets["energyKcal"]), 15)

    def test_energy_never_drops_below_the_safety_floor(self):
        small = profile(sex="female", heightCm=145.0, birthYear=1960, goal="fatLoss", activity="inactive")
        targets, notes = diet.targets_for(small, 40, NOW, TEST_POLICY, "setup")
        self.assertGreaterEqual(targets["energyKcal"], 1200)
        self.assertIn("ENERGY_AT_SAFETY_FLOOR", notes)

    def test_body_fat_adds_an_energy_availability_floor_only_when_given(self):
        lean = profile(goal="fatLoss", bodyFatPercent=10.0)
        requirement = diet.estimated_energy_requirement(lean, 80, NOW, TEST_POLICY)
        self.assertGreaterEqual(diet.energy_floor(lean, 80, requirement, TEST_POLICY), 30 * 72)

    def test_high_bmi_uses_the_reference_mass_for_protein(self):
        heavy = diet.protein_target(profile(goal="fatLoss"), 130, TEST_POLICY)
        self.assertAlmostEqual(heavy, 2.0 * 25 * 1.8 * 1.8)

    def test_vegan_multiplier_and_protein_ceiling(self):
        vegan = diet.protein_target(profile(goal="fatLoss", pattern="vegan"), 80, TEST_POLICY)
        self.assertAlmostEqual(vegan, 2.2 * 80)  # 2.0 x 1.1 = 2.2, the ceiling

    def test_protein_never_exceeds_its_share_of_energy(self):
        small = profile(sex="female", heightCm=150.0, birthYear=1990, goal="fatLoss", activity="inactive")
        targets, _ = diet.targets_for(small, 60, NOW, TEST_POLICY, "setup")
        self.assertLessEqual(targets["proteinG"] * 4, 0.35 * targets["energyKcal"] + 5)

    def test_fibre_stays_between_its_floor_and_ceiling(self):
        low, _ = diet.targets_for(profile(sex="female", heightCm=150.0, goal="fatLoss"), 50, NOW, TEST_POLICY, "setup")
        high, _ = diet.targets_for(profile(goal="endurance", trainingLoad="veryHigh"), 90, NOW, TEST_POLICY, "setup")
        self.assertEqual(low["fibreG"], 25)
        self.assertEqual(high["fibreG"], 40)

    def test_endurance_carbohydrate_follows_training_load(self):
        targets, _ = diet.targets_for(profile(goal="endurance", trainingLoad="high"), 70, NOW, TEST_POLICY, "setup")
        self.assertEqual(targets["carbohydrateG"], 8 * 70)
        self.assertGreaterEqual(targets["fatG"] * 9, 0.2 * targets["energyKcal"] - 10)


class TrendAndAdjustmentTests(unittest.TestCase):
    def state_with(self, goal, weekly_change_kg, decided_days_ago=20):
        state = golden_request()["payload"]["state"]
        state["dietProfile"] = profile(goal=goal)
        targets, _ = diet.targets_for(state["dietProfile"], 80, NOW - decided_days_ago * DAY, TEST_POLICY, "setup")
        state["dietTargets"] = targets
        state["weighIns"] = weigh_ins(80, weekly_change_kg)
        return state

    def test_trend_reads_the_weekly_rate(self):
        trend = diet.weight_trend(weigh_ins(80, -0.4), NOW, TEST_POLICY)
        self.assertAlmostEqual(trend["weeklyChangeKg"], -0.4, places=3)
        self.assertEqual(trend["weighIns"], 8)
        self.assertIsNone(diet.weight_trend(weigh_ins(80, -0.4)[:3], NOW, TEST_POLICY))

    def test_one_reading_per_local_day_and_an_even_spread(self):
        doubled = weigh_ins(80, -0.4) + [
            dict(w, id=uid(980 + i), kg=w["kg"] + 1.0, measuredAt=w["measuredAt"] + 3600)
            for i, w in enumerate(weigh_ins(80, -0.4))
        ]
        self.assertEqual(diet.weight_trend(doubled, NOW, TEST_POLICY)["weighIns"], 8)
        lumpy = [w for w in weigh_ins(80, -0.4, days=14, every=1) if w["measuredAt"] >= NOW - 6 * DAY]
        lumpy.append(weigh_ins(80, -0.4)[0])  # one old reading: the older week has too few days
        self.assertIsNone(diet.weight_trend(lumpy, NOW, TEST_POLICY))

    def test_unsafe_loss_is_flagged_before_the_waiting_period_ends(self):
        state = self.state_with("fatLoss", -1.2, decided_days_ago=8)
        state["weighIns"] = [w for w in weigh_ins(80, -1.2, days=8, every=1)]
        self.assertEqual(diet.adjustment_for(state, NOW, TEST_POLICY)["reason"], "LOSING_FASTER_THAN_SAFE")

    def test_only_weigh_ins_under_the_current_target_count(self):
        state = self.state_with("fatLoss", 0.0, decided_days_ago=20)
        state["dietDecisions"] = [
            {
                "id": uid(970),
                "kind": "adjustment",
                "targets": state["dietTargets"],
                "reason": "x",
                "decidedAt": NOW - 3 * DAY,
                "status": "rejected",
            }
        ]
        self.assertIsNone(diet.adjustment_for(state, NOW, TEST_POLICY))

    def test_slow_fat_loss_suggests_eating_less(self):
        adjustment = diet.adjustment_for(self.state_with("fatLoss", 0.0), NOW, TEST_POLICY)
        self.assertEqual(adjustment["reason"], "LOSING_SLOWER_THAN_GOAL")
        self.assertEqual(adjustment["targets"]["basis"], "adjustment")

    def test_unsafe_fat_loss_suggests_eating_more(self):
        adjustment = diet.adjustment_for(self.state_with("fatLoss", -1.2), NOW, TEST_POLICY)
        self.assertEqual(adjustment["reason"], "LOSING_FASTER_THAN_SAFE")

    def test_on_course_or_too_soon_suggests_nothing(self):
        self.assertIsNone(diet.adjustment_for(self.state_with("fatLoss", -0.4), NOW, TEST_POLICY))
        self.assertIsNone(diet.adjustment_for(self.state_with("fatLoss", 0.0, decided_days_ago=5), NOW, TEST_POLICY))

    def test_a_proposal_never_reverses_or_cancels_its_own_step(self):
        # Endurance carbohydrate is g/kg: at a heavier trend weight "eat less" would re-inflate energy.
        state = golden_request()["payload"]["state"]
        state["dietProfile"] = profile(goal="endurance", trainingLoad="veryHigh")
        state["dietTargets"], _ = diet.targets_for(state["dietProfile"], 80, NOW - 20 * DAY, TEST_POLICY, "setup")
        state["weighIns"] = weigh_ins(80, 0.6)
        adjustment = diet.adjustment_for(state, NOW, TEST_POLICY)
        self.assertTrue(adjustment is None or adjustment["targets"]["energyKcal"] < state["dietTargets"]["energyKcal"])
        # At a binding floor the step rounds away: nothing to suggest.
        floored = self.state_with("fatLoss", 0.0)
        floored["dietProfile"]["bodyFatPercent"] = 5.0
        floor = diet.energy_floor(floored["dietProfile"], 80, 0, TEST_POLICY)
        floored["dietTargets"] = diet.macros_for(
            floor, floored["dietProfile"], 80, NOW - 20 * DAY, TEST_POLICY, "setup", [], floor=floor
        )
        self.assertIsNone(diet.adjustment_for(floored, NOW, TEST_POLICY))

    def test_a_binding_floor_rounds_up_never_down(self):
        targets = diet.macros_for(2162.7, profile(), 80, NOW, TEST_POLICY, "setup", [], floor=2162.7)
        self.assertEqual(targets["energyKcal"], 2170)

    def test_fat_loss_is_unavailable_when_the_floor_meets_the_need(self):
        lean = profile(goal="fatLoss", bodyFatPercent=5.0, activity="inactive", birthYear=1950)
        _, notes = diet.targets_for(lean, 90, NOW, TEST_POLICY, "setup")
        self.assertIn("FAT_LOSS_NOT_AVAILABLE", notes)

    def test_adjustment_copy_states_the_real_window_and_protein_change(self):
        state = self.state_with("fatLoss", -1.2, decided_days_ago=8)
        state["weighIns"] = weigh_ins(80, -1.2, days=8, every=1)
        body = diet.adjustment_for(state, NOW, TEST_POLICY)["body"]
        self.assertIn("last 8 days", body)
        self.assertIn("protein moves from", body)

    def test_a_quicker_pace_suggests_sooner_on_fewer_days(self):
        state = self.state_with("fatLoss", 0.0, decided_days_ago=8)
        state["weighIns"] = weigh_ins(80, 0.0, days=8, every=1)
        self.assertIsNone(diet.adjustment_for(state, NOW, TEST_POLICY))  # slower: 14-day wait
        state["dietProfile"]["pace"] = "standard"
        self.assertEqual(diet.adjustment_for(state, NOW, TEST_POLICY)["reason"], "LOSING_SLOWER_THAN_GOAL")

    def test_maintenance_drift_is_corrected_toward_stable(self):
        adjustment = diet.adjustment_for(self.state_with("maintenance", 0.5), NOW, TEST_POLICY)
        self.assertEqual(adjustment["reason"], "WEIGHT_RISING")


class SafetyTests(unittest.TestCase):
    def test_exclusions_withhold_targets(self):
        cases = {
            "pregnancy": profile(
                screening={"pregnant": True, "lactating": False, "conditions": [], "scoffAnswers": [False] * 5}
            ),
            "eatingDisorderRisk": profile(
                screening={
                    "pregnant": False,
                    "lactating": False,
                    "conditions": [],
                    "scoffAnswers": [True, True, False, False, False],
                }
            ),
            "chronicKidneyDisease": profile(
                screening={
                    "pregnant": False,
                    "lactating": False,
                    "conditions": ["chronicKidneyDisease"],
                    "scoffAnswers": [False] * 5,
                }
            ),
            "underMinimumAge": profile(birthYear=2012),
        }
        for expected, candidate in cases.items():
            self.assertEqual(diet.safety_block(candidate, NOW, TEST_POLICY), expected)
        self.assertIsNone(diet.safety_block(profile(), NOW, TEST_POLICY))

    def test_weigh_ins_trigger_exclusions_the_athlete_did_not_tick(self):
        light = weigh_ins(55, 0.0)
        self.assertEqual(diet.safety_block(profile(), NOW, TEST_POLICY, light), "lowBmi")  # 55 kg at 1.80 m: BMI 17.0
        slim = weigh_ins(59, 0.0)
        self.assertEqual(diet.safety_block(profile(goal="fatLoss"), NOW, TEST_POLICY, slim), "lowBmiForFatLoss")
        self.assertIsNone(diet.safety_block(profile(goal="maintenance"), NOW, TEST_POLICY, slim))
        falling = [dict(w, kg=90 - 10 * i / 7) for i, w in enumerate(weigh_ins(90, 0.0))]  # -10 kg in 14 days
        self.assertEqual(diet.safety_block(profile(), NOW, TEST_POLICY, falling), "rapidRecentWeightLoss")


class DietCommandTests(PolicyPatch):
    def state(self):
        return golden_request()["payload"]["state"]

    def command(self, state, name, arguments, now=NOW):
        payload = {
            "command": name,
            "arguments": arguments,
            "state": state,
            "permitsFixtures": True,
            "now": now,
            "ids": [uid(n) for n in range(400, 410)],
        }
        return call("stateCommand", payload)

    def test_targets_need_a_weigh_in_and_must_match_what_was_shown(self):
        state = self.state()
        self.assertEqual(
            result("dietPreview", {"state": state, "profile": profile(), "now": NOW})["status"], "needsInput"
        )
        state = self.command(state, "logWeighIn", {"weighIn": weigh_ins(80, 0)[-1]})["result"]["state"]
        preview = result("dietPreview", {"state": state, "profile": profile(), "now": NOW})
        stale = dict(preview["targets"], energyKcal=preview["targets"]["energyKcal"] + 10)
        self.assertEqual(
            self.command(copy.deepcopy(state), "setDietTargets", {"profile": profile(), "expected": stale})["error"][
                "code"
            ],
            "staleProposal",
        )
        accepted = self.command(state, "setDietTargets", {"profile": profile(), "expected": preview["targets"]})[
            "result"
        ]["state"]
        self.assertEqual(accepted["dietTargets"]["energyKcal"], preview["targets"]["energyKcal"])
        self.assertEqual(accepted["dietDecisions"][0]["status"], "applied")

    def test_withheld_profiles_cannot_set_targets(self):
        state = self.command(self.state(), "logWeighIn", {"weighIn": weigh_ins(80, 0)[-1]})["result"]["state"]
        risky = profile(
            screening={
                "pregnant": False,
                "lactating": False,
                "conditions": [],
                "scoffAnswers": [True, True, True, False, False],
            }
        )
        preview = result("dietPreview", {"state": state, "profile": risky, "now": NOW})
        self.assertEqual((preview["status"], preview["reason"]), ("withheld", "eatingDisorderRisk"))

    def test_a_pace_change_keeps_the_targets_and_their_date(self):
        state = self.command(self.state(), "logWeighIn", {"weighIn": weigh_ins(80, 0)[-1]})["result"]["state"]
        preview = result("dietPreview", {"state": state, "profile": profile(), "now": NOW})
        state = self.command(state, "setDietTargets", {"profile": profile(), "expected": preview["targets"]})["result"][
            "state"
        ]
        later = NOW + 3 * DAY
        quicker = profile(pace="standard")
        again = result("dietPreview", {"state": state, "profile": quicker, "now": later})
        changed = self.command(state, "setDietTargets", {"profile": quicker, "expected": again["targets"]}, now=later)[
            "result"
        ]["state"]
        self.assertEqual(changed["dietProfile"]["pace"], "standard")
        self.assertEqual(changed["dietTargets"]["setAt"], NOW)

    def test_answers_that_withhold_targets_can_always_be_saved(self):
        state = self.command(self.state(), "logWeighIn", {"weighIn": weigh_ins(80, 0)[-1]})["result"]["state"]
        preview = result("dietPreview", {"state": state, "profile": profile(), "now": NOW})
        state = self.command(state, "setDietTargets", {"profile": profile(), "expected": preview["targets"]})["result"][
            "state"
        ]
        pregnant = profile(
            screening={"pregnant": True, "lactating": False, "conditions": [], "scoffAnswers": [False] * 5}
        )
        saved = self.command(state, "saveDietProfile", {"profile": pregnant})["result"]["state"]
        self.assertNotIn("dietTargets", saved)
        self.assertEqual(
            result("views", {"state": saved, "permitsFixtures": True, "now": NOW})["diet"]["status"], "withheld"
        )

    def test_preview_validates_the_profile(self):
        state = self.command(self.state(), "logWeighIn", {"weighIn": weigh_ins(80, 0)[-1]})["result"]["state"]
        for bad in ({"heightCm": 0.0}, {"birthYear": 0}, {"goal": "endurance"}):
            reply = call("dietPreview", {"state": state, "profile": profile(**bad), "now": NOW})
            self.assertEqual(reply["error"]["code"], "invalid", bad)

    def test_implausible_or_future_weigh_ins_are_refused(self):
        for bad in ({"kg": 5.0}, {"kg": 80.0, "measuredAt": NOW + 3 * DAY}, {"kg": 80.0, "source": "scale"}):
            weigh_in = dict(weigh_ins(80, 0)[-1], **bad)
            self.assertEqual(
                self.command(self.state(), "logWeighIn", {"weighIn": weigh_in})["error"]["code"], "invalid"
            )

    def test_apple_health_import_skips_bad_and_deleted_samples(self):
        samples = [dict(w, source="appleHealth") for w in weigh_ins(80, 0)]
        with_bad = [*samples, dict(samples[0], id=uid(999), kg=5.0, measuredAt=NOW - 3600)]
        state = self.command(self.state(), "importWeighIns", {"weighIns": with_bad})["result"]["state"]
        self.assertEqual(len(state["weighIns"]), len(samples))
        state = self.command(state, "deleteWeighIn", {"id": samples[-1]["id"]})["result"]["state"]
        again = self.command(
            state, "importWeighIns", {"weighIns": [dict(w, id=uid(1100 + i)) for i, w in enumerate(samples)]}
        )
        self.assertEqual(len(again["result"]["state"]["weighIns"]), len(samples) - 1)

    def test_apple_health_import_skips_duplicates(self):
        imported = [dict(w, source="appleHealth") for w in weigh_ins(80, 0)]
        once = self.command(self.state(), "importWeighIns", {"weighIns": imported})["result"]
        self.assertTrue(once["value"])
        again = self.command(
            once["state"], "importWeighIns", {"weighIns": [dict(w, id=uid(990 + i)) for i, w in enumerate(imported)]}
        )["result"]
        self.assertFalse(again["value"])
        self.assertEqual(len(again["state"]["weighIns"]), len(imported))

    def test_adjustments_apply_only_when_accepted_and_rejection_waits(self):
        state = self.state()
        state["dietProfile"] = profile(goal="fatLoss")
        state["dietTargets"], _ = diet.targets_for(state["dietProfile"], 80, NOW - 20 * DAY, TEST_POLICY, "setup")
        state["weighIns"] = weigh_ins(80, 0.0)
        view = result("views", {"state": state, "permitsFixtures": True, "now": NOW})["diet"]
        suggested = view["adjustment"]["targets"]
        self.assertLess(suggested["energyKcal"], state["dietTargets"]["energyKcal"])
        rejected = self.command(copy.deepcopy(state), "rejectDietAdjustment", {"expected": suggested})["result"][
            "state"
        ]
        self.assertEqual(rejected["dietTargets"], state["dietTargets"])
        self.assertNotIn(
            "adjustment", result("views", {"state": rejected, "permitsFixtures": True, "now": NOW})["diet"]
        )
        accepted = self.command(state, "acceptDietAdjustment", {"expected": suggested})["result"]["state"]
        self.assertEqual(accepted["dietTargets"]["energyKcal"], suggested["energyKcal"])

    def test_food_meals_take_nutrients_from_the_table(self):
        tofu = foods.search("tofu raw firm", "vegan", 1)[0]
        arguments = {"id": uid(950), "foodID": tofu["id"], "grams": 150, "occurredAt": NOW, "timeZone": "UTC"}
        meal = self.command(self.state(), "saveFoodMeal", arguments)["result"]["state"]["meals"][-1]
        self.assertEqual(meal["nutrients"], foods.nutrients_per(foods.food(tofu["id"]), 150.0))
        self.assertEqual(meal["source"], f"fdc:{tofu['id']}")
        missing = dict(arguments, id=uid(951), foodID=-1)
        self.assertEqual(self.command(self.state(), "saveFoodMeal", missing)["error"]["code"], "notFound")


class FoodTests(unittest.TestCase):
    def test_search_filters_by_pattern(self):
        self.assertTrue(foods.search("chicken breast", None, 5))
        self.assertEqual(foods.search("chicken breast", "vegan", 5), [])
        self.assertEqual(foods.search("   ", None, 5), [])

    def test_suggestions_fit_the_energy_left_and_the_pattern(self):
        targets = {"energyKcal": 2400, "proteinG": 160}
        remaining = {"calories": 400.0, "protein": 90.0, "carbs": 50.0, "fat": 10.0}
        vegan = profile(pattern="vegan", cuisines=["indian"])
        suggested = foods.suggest(remaining, targets, vegan, TEST_POLICY)
        self.assertTrue(suggested)
        for suggestion in suggested:
            self.assertLessEqual(suggestion["nutrients"]["calories"], 400)
            self.assertIn("vegan", foods.food(suggestion["foodID"])["patterns"])
        self.assertEqual(foods.suggest(dict(remaining, calories=0.0), targets, vegan, TEST_POLICY), [])


class DietViewTests(PolicyPatch):
    def test_view_states(self):
        state = golden_request()["payload"]["state"]
        self.assertEqual(diet_view.diet_view(state, NOW, None)["reason"], "NO_DIET_PROFILE")
        state["dietProfile"] = profile()
        self.assertEqual(diet_view.diet_view(state, NOW, None)["reason"], "NO_DIET_TARGETS")
        state["dietTargets"], _ = diet.targets_for(profile(), 80, NOW, TEST_POLICY, "setup")
        state["meals"] = [
            {
                "id": uid(960),
                "revision": 1,
                "name": "x",
                "occurredAt": NOW - 3600,
                "source": "user_estimate",
                "timeZone": "UTC",
                "nutrients": {"calories": 500, "protein": 30, "carbs": 50, "fat": 20},
            }
        ]
        view = diet_view.diet_view(state, NOW, NOW - 7200)
        self.assertEqual(view["status"], "ready")
        self.assertEqual(view["remaining"]["calories"], state["dietTargets"]["energyKcal"] - 500)
        self.assertEqual(diet_view.diet_view(state, NOW, NOW - 1800)["eaten"]["calories"], 0)
        state["meals"][0]["occurredAt"] = NOW + 3600  # planned later today still counts today
        self.assertEqual(diet_view.diet_view(state, NOW, NOW - 7200)["eaten"]["calories"], 500)


class ShippedDietBundleTests(unittest.TestCase):
    def test_every_shipped_diet_bundle_passes_the_gate(self):
        bundles = diet_content.all_bundles()
        self.assertTrue(bundles, "a diet bundle ships with the core")
        for bundle_id, (manifest, body) in bundles.items():
            with self.subTest(bundle_id):
                self.assertEqual(diet_content.bundle_problems(manifest, body), [])

    def test_shipped_policy_builds_valid_views(self):
        self.assertIsNotNone(diet_content.active_policy())
        options = result("dietOptions", {"now": NOW})
        self.assertTrue(options["activityLevels"] and options["scoffQuestions"])
        state = golden_request()["payload"]["state"]
        state["weighIns"] = weigh_ins(80, 0)
        preview = result("dietPreview", {"state": state, "profile": profile(goal="fatLoss"), "now": NOW})
        self.assertEqual(preview["status"], "ready")
        self.assertTrue(preview["citations"])


if __name__ == "__main__":
    unittest.main()
