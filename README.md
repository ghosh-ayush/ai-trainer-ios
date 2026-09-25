# AI Trainer

A local-first iPhone app for resistance training and diet, built as a monorepo with a Python
domain core and a native SwiftUI client. The app embeds CPython and calls it **in process**,
through a small C bridge and versioned JSON contracts. There is no server, account, API key or
runtime download, and no network at runtime: everything works offline after installation.

Every suggestion traces to cited research and nothing else. Training and diet guidance ship in
content bundles whose every value cites a peer-reviewed source with a locator and a certainty
grade; an automated evidence gate refuses anything uncited (ADR-014). Where the literature gives
no number, the value is marked as the app's own rule, with a rationale built from cited sources.
Any plan change is a proposal the athlete accepts. The working agreement for people and coding
agents is [AGENTS.md](AGENTS.md).

## What the app does

The app has four tabs: **Today**, **Diet**, **Progress** and **You**.

- **Weekly plan (ADR-017).** The athlete picks their free weekdays (1 to 7) and minutes. The core
  offers up to three weeks within the bundle's research bounds, previews each by weekday, and
  builds the one the athlete accepts.
- **Changing free days (ADR-025).** The first choice is only a starting point: new days and minutes
  get a proposed week, with confirmed loads carried over.
- **Adapting to training history (ADR-018).** After two full weeks, a week that fits what the
  athlete actually did is proposed: fewer or more sessions, shorter sessions, or their real
  training days.
- **Progression.** A conservative double progression on confirmed, comparable sets. Load, reps
  in reserve and effort are never estimated; unknown stays unknown.
- **Today.** One-tap start, less time, move day, skip, "I'm in pain", a break, sickness or injury
  status that pauses the app's own suggestions (ADR-019), muscle rings for this week's logged sets
  (ADR-020), and a chat head.
- **Workout.** "Same as last", last time's numbers, plates per side (ADR-021), an optional spoken
  coach (ADR-022), and logging a set in words with Apple's on-device model (ADR-015).
- **Chat (ADR-023).** Ask about progress, the week, time, pain or where the numbers come from.
  The on-device model only sorts the message into a topic; the core writes every answer from the
  athlete's records and the cited content, and nothing changes until a button is tapped.
- **Diet (ADR-016).** Daily targets from a cited diet bundle, withheld for anyone the policy
  excludes, foods from the bundled USDA table, weight-trend suggestions, and vegetarian, vegan
  and cuisine options.

Apple's on-device model is used only to read words, never to decide. Typed chat and set logging
need Apple Intelligence; chat also works by tapping questions. Camera rep counting and HealthKit
recovery are Debug-only labs, and recovery stays `unassessed` because no cited readiness rule
fits the data HealthKit provides (`docs/research/readiness-evidence.md`).

## Structure

```text
apps/ios/App/                    SwiftUI app, native services and the Xcode project (Xcode owns it, ADR-011)
apps/ios/Sources/AITrainerCore/   Generated Swift models, service facade, storage, design system, on-device readers
apps/ios/PythonBridge/           CPython C API bridge (GIL and memory ownership)
apps/ios/Tests/                  Swift tests through the real embedded interpreter
apps/ios/App/AITrainerUITests/   UI tests that drive the real app (XCUITest)
apps/ios/Vendor/                 Ignored, checksum-pinned CPython build artifact
core/python/ai_trainer/          Domain core: rules, state commands, views, chat, contract spec, migrations
  bundles/<id>/                  Cited training content (evidence-2 approved, evidence-1 disabled, fixture-1 test data)
  diet_bundles/<id>/             Cited diet policy (diet-1)
  data/foods.json                USDA FoodData Central extract (CC0)
core/python/tests/               Python behaviour and contract tests
shared/fixtures/v1/              Cross-language golden contract fixtures
docs/                            Specification, ADRs, architecture, research evidence, content review sheets
scripts/                         Setup, packaging, schema and model generation, data builders, tests, smoke test
ml/                              Reserved for future offline model tooling (empty)
Package.swift                    Swift package entry point
```

The Swift⇄Python contract is defined once in `core/python/ai_trainer/contract_spec.py`. The JSON
schemas and `apps/ios/Sources/AITrainerCore/Models.swift` are generated from it, and CI fails if
they drift.

## Run in Xcode

1. On a Mac with Xcode 16+ and an iOS 17+ SDK, run `scripts/setup_python.sh` from the repository
   root. It downloads the checksum-verified BeeWare Python 3.13.11 (`3.13-b13`) build into the
   ignored `apps/ios/Vendor/` directory; an offline archive can be passed as the first argument.
   This is a developer setup step, not an app network requirement.
2. Open **`apps/ios/App/AITrainer.xcodeproj`**, choose the **AITrainer** scheme, an iPhone
   simulator and **Debug**, then Run. Keep the whole monorepo together. If Xcode reports a
   duplicate local package or a missing `AITrainerCore` product, close other windows that have the
   root `Package.swift` open.
3. Xcode resolves the pinned RepCounterSDK package once. The build embeds Python.framework, the
   standard library, the pure-Python core, its schemas and the content bundles. No pip packages
   are installed in the app.
4. Complete onboarding: pick your free days, minutes and equipment, preview the suggested weeks
   and accept one. Confirm familiar loads when asked; the app never estimates them.
5. For a physical iPhone, choose your development team and bundle identifier under Signing &
   Capabilities. Provisioning must support HealthKit.

Both Debug and Release run the approved `evidence-2` bundle. The `fixture-1` test content runs
only in Debug, when tests pin it or no approved bundle exists; Release refuses it.

Files under `apps/ios/Sources` and `apps/ios/Tests` are discovered by the package automatically.
Files under `apps/ios/App/AITrainer` belong to the app target and must be added through Xcode.

## Tests and builds

Python tests run on macOS or Linux without Xcode or the downloaded framework:

```sh
PYTHONPATH=core/python python3 -m unittest discover -s core/python/tests -v
```

On macOS, with a Python that includes matching headers and libpython
(`python3-config --embed --ldflags`), run the Python and Swift tests together:

```sh
scripts/setup_python.sh
scripts/test.sh
```

`PYTHON_CONFIG=/path/to/python3-config scripts/test.sh` selects that installation. The Swift tests
run through the **real C bridge and embedded interpreter**. One test runs Apple's on-device model
through the core and is skipped where the model is unavailable.

After changing `contract_spec.py`, regenerate and commit the schemas and Swift models:

```sh
python3 scripts/generate_schemas.py
python3 scripts/generate_swift_models.py
```

A simulator build and the smoke test:

```sh
xcodebuild -project apps/ios/App/AITrainer.xcodeproj -scheme AITrainer \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath DerivedData \
  CODE_SIGNING_ALLOWED=NO ARCHS=arm64 build
scripts/smoke_ios.sh BOOTED_SIMULATOR_UUID
```

UI tests drive the real app through onboarding, set logging and chat (ADR-024). Each test launches
with the Debug-only `--ui-testing` flag, which starts from an empty in-memory state:

```sh
xcodebuild test -project apps/ios/App/AITrainer.xcodeproj -scheme AITrainer -sdk iphonesimulator \
  -destination 'id=BOOTED_SIMULATOR_UUID' -only-testing:AITrainerUITests \
  -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO
```

The Debug-only smoke mode uses an in-memory repository and writes
`Documents/core-smoke-result.json` in the simulator app container without touching saved athlete
data.

CI runs four jobs: `changes`, then `python` (tests, ruff, mypy and a check that generated files are
current), `swift-tests`, and `simulator` (Debug build, smoke test, UI tests and a Release build). The two
macOS jobs are skipped for documentation-only changes.

## Architecture

Python owns the rules: plan selection and the weekly planner, progression, adaptation, the
proposal lifecycle with re-evaluation on accept, workout and state commands, corrections and
conflicts, statuses, diet targets and adjustments, food search, the spoken coach's words, and
chat answers. Swift owns the UI, sensors and perception, the on-device model readers, Codable
models and durable local saves. `TrainerService` delegates to `LocalPythonTrainerService`, and
`TrainerCoreTransport.exchange(Data)` is the replaceable boundary.

- [Architecture](docs/LOCAL_PYTHON_ARCHITECTURE.md)
- [Decisions (ADRs)](docs/DECISIONS.md)
- [Migration notes and limitations](docs/PYTHON_MIGRATION.md)
- [Open-source boundaries and licences](docs/OPEN_SOURCE_INTEGRATION.md)
- [Physical-device checklist](docs/DEVICE_TEST_PLAN.md)
- [Original product specification](docs/AI_Trainer_01_Athlete_State_and_Training_Brain.md)
- Research evidence: `docs/research/`; content review sheets: `docs/content/`
