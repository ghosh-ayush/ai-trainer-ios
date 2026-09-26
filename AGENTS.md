# AGENTS.md — working agreement for humans and coding agents (Claude, Codex, others)

This file is the single source of truth for how to work in this repository.
`CLAUDE.md` imports it; Codex reads it directly. Keep the two in sync by editing only this file.

## What this project is
AI Trainer: a local-first iPhone resistance-training app. Domain rules run in **embedded CPython**
(`core/python/ai_trainer`); Swift owns UI, persistence, camera, HealthKit (`apps/ios`). No backend,
no network at runtime, no LLM in the decision path. Product spec: `docs/AI_Trainer_01_*.md`.
Architecture: `docs/LOCAL_PYTHON_ARCHITECTURE.md`. Decisions: `docs/DECISIONS.md`.

## Non-negotiable rules
1. **Every suggestion traces to well-cited research, and nothing else.** The app adapts exercise
   and diet guidance to the athlete automatically, and every rule and number behind that guidance
   (exercises and their selection, templates, rep/set/RIR/rest values, progression and adaptation
   thresholds, nutrition targets) ships from a content bundle or evidence file whose every value
   cites a qualifying source with a locator and a certainty grade (ADR-014).
   - **Qualifying source:** a peer-reviewed human study or official reference report with a DOI or
     PMID (an official report may cite its ISBN): position stand, official guideline (DRI, FAO/WHO), umbrella review, meta-analysis,
     systematic review, randomised, crossover or non-randomised trial, cohort or cross-sectional
     study, or narrative review (`content.QUALIFYING_DESIGNS`). Each is read from the paper itself
     (PubMed, PMC, publisher or DOI) and independently re-checked against it before it is used.
     Only a synthesis or official reference may be graded above low certainty.
   - **Never a source:** videos, influencers, blogs, forums, podcasts, apps, preprints, animal or
     cadaver studies, opinion columns, AI-generated text or any "the internet says". They may point
     you to a paper; the paper is what gets cited.
   - No human approval step: content goes live automatically once `content.bundle_problems` finds
     nothing. Where the literature gives no number, the value is marked `"source": "owner"` with a
     rationale built from cited sources; never a bare guess.
   - Fixture values are test data; they must not become defaults. Release builds refuse
     `review: fixture` content — keep it that way.
2. **Unknown stays unknown.** `load`, `rir`, effort and any sensor-derived value are optional.
   Never default them to favourable values or estimate strength.
3. **Proposals, not mutations.** The app suggests changes automatically, but any plan change is a
   `Recommendation` that the user explicitly accepts. Acceptance re-evaluates the stored request
   and requires an identical decision.
4. **Sensors never write evidence.** Camera, HealthKit and nutrition data never become `SetLog`
   records or stand in for what the athlete logged; load progression reads only logged sets.
   Lifestyle signals (sleep, activity, nutrition, schedule) may shape suggestions only through a
   rule whose thresholds are cited under rule 1. Catalog research annotations (`evidence`) may
   inform exercise selection and substitution; the catalog's upstream descriptions never do.
5. **Licenses.** Only MIT / BSD / Apache-2.0 / Unlicense / public-domain / CC0 code and data.
   Fonts may also be SIL OFL-1.1, bundled unmodified (ADR-013). No AGPL, GPL, LGPL, SSPL,
   PolyForm, CC-BY-SA data, or unlicensed datasets — not even as a reference implementation. Add every new dependency or dataset to
   `apps/ios/Sources/AITrainerCore/Resources/ThirdPartyNotices.txt`.
6. **Python first.** New logic goes in `core/python` unless it is UI, per-frame perception,
   platform I/O (files, CloudKit, HealthKit, camera) or a Codable DTO. Swift is a thin client.
7. **No secrets, no credentials, no personal health data** in the repo, fixtures or tests.

## Repository map
```
core/python/ai_trainer/   domain rules, state commands, content bundle, migrations, contract schemas
  diet*.py, foods.py      diet engine (targets, trend, adjustments, safety) and USDA food search/suggestions
  diet_bundles/<id>/      cited diet policy (same evidence gate as training bundles)
  data/foods.json         USDA FoodData Central extract (CC0), built by scripts/build_food_data.py
core/python/tests/        Python behaviour + contract tests (fast; run these constantly)
shared/fixtures/v1/       golden request/response fixtures
apps/ios/App/             SwiftUI app + AITrainer.xcodeproj (Xcode owns it; see ADR-011)
apps/ios/App/AITrainerUITests/  UI tests driving the real app (folder-synchronised: new files join automatically)
apps/ios/Sources/AITrainerCore/   Swift DTOs, transport to Python, persistence, perception
apps/ios/PythonBridge/    C bridge to CPython (rarely changes)
apps/ios/Vendor/          gitignored: Python.xcframework from scripts/setup_python.sh
scripts/                  setup, bundling, generation, tests, simulator smoke
docs/                     spec, architecture, migration notes, device test plan, ADRs
```

## Setup (once per clone)
```
scripts/setup_python.sh                 # downloads the pinned CPython xcframework (macOS)
```
Nothing in `apps/ios` builds until that has run.

## Commands
```
PYTHONPATH=core/python python3 -m unittest discover -s core/python/tests -v   # Python tests (Linux/macOS)
scripts/test.sh                          # Python + Swift tests through embedded CPython (macOS)
python3 scripts/generate_schemas.py      # after ANY change to contract_spec.py; CI diffs ai_trainer/*.schema.json
python3 scripts/generate_swift_models.py # after ANY change to contract_spec.py; CI diffs Models.swift
python3 scripts/annotate_catalog.py      # after ANY change to docs/research/exercise-evidence.json
python3 scripts/content_review_sheet.py <bundle-id>  # after ANY change to a content bundle
python3 scripts/build_food_data.py <dir> # rebuild data/foods.json from unzipped USDA FDC downloads
open apps/ios/App/AITrainer.xcodeproj    # scheme AITrainer, Debug, iPhone simulator
scripts/smoke_ios.sh <BOOTED_SIM_UUID>   # after a Debug build
xcodebuild test -project apps/ios/App/AITrainer.xcodeproj -scheme AITrainer -sdk iphonesimulator \
  -destination 'id=<SIM_UUID>' -only-testing:AITrainerUITests -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO
                                         # UI tests (ADR-024); each launches with --ui-testing
```

## Workflow
- Branch per task: `claude/<topic>`, `codex/<topic>`, `feat/<topic>`. Never commit to `master`.
- One PR per change; CI (`python`, `swift-tests` and `simulator` jobs) must be green; squash-merge.
- Definition of done: tests added/updated · schemas and Models.swift regenerated if the contract
  spec changed · new app-target files added through Xcode · docs touched if behaviour changed · ADR in
  `docs/DECISIONS.md` if an architectural or product-policy decision was made · notices updated
  if a dependency was added.
- Keep the Swift⇄Python contract at version `1.0` unless an ADR says otherwise.
- Prefer small, readable code over clever one-liners. Descriptive names; a docstring per public
  function; no semicolon-chained statements. Agents: do not compress code to save tokens.
- Swift never reaches for a global core. `AppStore` composes the one `LocalPythonTrainerService`
  and passes it down (`TrainerService.core`, `ExerciseCatalog.bundled(core:)`, …). Tests build
  their own instance. Do not reintroduce a `.shared` singleton.
- Do not hand-edit or regenerate `AITrainer.xcodeproj`; add app-target files in Xcode. Package
  files under `apps/ios/Sources` and `apps/ios/Tests` are discovered automatically.
- Do not run `rm -rf` on `apps/ios/Vendor` or `DerivedData` in someone else's checkout.

## Things that look like bugs but are intentional
- Release builds cannot activate a plan until an `approved` content bundle exists. Bundles live in
  `ai_trainer/bundles/<id>/` (`manifest.json` + `content.json`). `approved` means the bundle passed
  the automated evidence gate, not that a person signed it (ADR-014): it always runs, the fixture
  runs only in Debug, and a `draft` (research still in progress) never runs. The gate refuses any
  uncited value and any source without a DOI/PMID and a qualifying design;
  `scripts/content_review_sheet.py <id>` writes a transparency sheet of what each value rests on.
- Tests pin the fixture with `AI_TRAINER_CONTENT_BUNDLE=fixture-1` (`support.py`, `scripts/test.sh`,
  `scripts/smoke_ios.sh`), so rule tests do not change whenever research updates shipped content.
  Pinning never bypasses a gate: only the fixture (still Debug-only) or an approved bundle can be pinned.
- Recovery observations always return `unassessed` (no cited readiness policy yet).
- Diet targets need a weigh-in and are withheld (never estimated) for anyone the diet policy
  excludes: under 18, pregnancy, breastfeeding, a positive SCOFF screen, or a listed condition.
  Logged meals are shown against the targets but never used to recompute energy, because
  self-reported intake is systematically low. Weight-trend adjustments are suggestions only.
- Food nutrients always come from the bundled USDA table (`saveFoodMeal`); the host sends a food
  id and grams, never nutrient values, except for the athlete's own estimates via `saveMeal`.
- Curl counter reps are never saved as sets.
- Today requests a slot's progression proposal automatically when the core's `views` names
  it (`autoRequest`). It is still only a proposal: nothing changes until the athlete taps Accept.
- A one-tap "Done as planned" set records the planned reps and load with RIR unknown; effort is
  never assumed. "4+" RIR is recorded as 4.
- "Log a set in words" appears only where Apple's on-device model runs. `readSet` drops any
  number the athlete did not say, even one the model returned, and nothing saves until Save (ADR-015).
- Chat (ADR-023, ADR-027): the on-device model sorts a message into a topic and then rewords the
  core's answer. `chat` keeps a number or an exercise only if the athlete said it, answers pain words
  as pain whatever the model chose, and computes every fact from records and cited content.
  `checkChatWording` refuses any rewording with a number or exercise not in the facts, and pain
  answers are never reworded. The facts stay one tap away; replies change nothing until an action is
  tapped, and "lighter week" gets no invented rule.
- Weekly plans (ADR-017) never guess weekdays: onboarding starts with no free day selected, and a
  migrated profile keeps `freeDays` absent. Seven free days give at most six sessions (no qualifying
  7-day trial); the cap is a cited owner decision in the bundle, not code.
- A week that fits recent training (ADR-018) is proposed only after the week has run 14 days, from
  logged sessions only (a skipped session or an empty day is a miss), and never applied without Accept.
  Weekday habits need the host's UTC offset (sent with `views` and the replan request); without it they
  stay unknown. "Ended early for time" counts only when the athlete chose the "time" reason.
- A break, illness or injury (ADR-019) pauses only what the app proposes on its own; the athlete's
  own requests still run, the plan never changes, and status days never count as missed sessions.
- Free days can change at any time (ADR-025), but only as a proposed week the athlete accepts.
  Confirmed loads carry over to the same exercise on the same equipment; unconfirmed ones stay unknown.
- A different session today (ADR-026) swaps two sessions' days on Accept. Its 72-hour notice is the
  owner's own value with no study behind it, and is labelled so; only the back-to-back limit is cited.
  Neither note blocks the athlete's choice.
- `evidence-1` is `disabled`, superseded by `evidence-2` (the weekly planner); only one bundle may
  be `approved` at a time.
- Dates cross the bridge as binary64 seconds since 2001-01-01 (Foundation reference epoch).
- Swift has no validators of its own: set and nutrient rules run in Python when a command is
  saved, so a malformed set is rejected by `saveSet`, not by a Swift `validate()`.
- Swift never sends training content. It passes `permitsFixtures`; Python loads the active bundle
  (exercises, policy, program template) itself.
- Saved state files are upgraded by Python (`migrations.py`) before Swift decodes them. Bump
  `STATE_SCHEMA_VERSION` in `contract_spec.py` and add a migration step for any stored-shape change.
