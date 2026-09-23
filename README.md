# AI Trainer

A local-first monorepo with a Python domain core and a native SwiftUI iPhone app.
The app embeds CPython and calls it **in process**, through a small C bridge and
versioned JSON contracts. There is no HTTP server, AWS dependency, required API,
account, API key, or runtime download. All training and catalog functionality works
offline after installation. Camera/Vision/RepCounterSDK processing stays native.

This remains a development preview: Debug explicitly permits the existing numerical
fixtures; Release rejects fixture program activation. No reviewed training policy,
validated form analysis, readiness score or production prescription was invented.

## Structure

```text
apps/ios/App/                    SwiftUI app, native services and Xcode project
apps/ios/Sources/AITrainerCore/   Swift DTOs, local storage, service facade, perception
apps/ios/PythonBridge/           CPython C API bridge (GIL and memory ownership)
apps/ios/Tests/                  Swift regression and real embedded-runtime tests
apps/ios/Vendor/                 Ignored, checksum-pinned CPython build artifact
core/python/ai_trainer/          Training Brain, progression, state reducers, nutrition
core/python/tests/               Python unit and contract tests
shared/schemas/v1/               Explicit versioned request/response JSON schemas
shared/fixtures/v1/              Cross-language golden contract fixtures
ml/                             Future offline model training/export workspace
docs/                           Architecture, migration, specifications, device testing
scripts/                        Setup, packaging, schema generation, tests and smoke test
Package.swift                   Native package entry point
```

## Run in Xcode

1. On a Mac with Xcode 16+ and an iOS 17+ SDK/runtime, run
   `scripts/setup_python.sh` from the repository root. This downloads the
   checksum-verified BeeWare Python 3.13.11 / `3.13-b13` build into the ignored
   `apps/ios/Vendor/` directory. An offline archive can be supplied as the first
   argument. This is a developer setup step, not an app network requirement.
2. Open **`apps/ios/App/AITrainer.xcodeproj`**, choose **AITrainer**, an iPhone
   simulator, and **Debug**, then Run. Keep the entire monorepo together. Close
   other Xcode windows that have the root `Package.swift` open if Xcode reports
   a duplicate local package or missing `AITrainerCore` product.
3. Xcode resolves the pinned RepCounterSDK package once. The build automatically
   embeds Python.framework, the standard library, the pure Python core and its
   schemas. The packaging step is offline; no pip packages are installed in the app.
4. Complete onboarding and explicitly accept the fixture plan. The current fixture
   supports 2–4 days/week and at least 41 minutes; choose 60 for an optional slot.
   Confirm familiar loads and available equipment values, log workouts, then review
   and accept recommendations. Unknown values remain blank.
5. For a physical iPhone, choose your development team and bundle identifier in
   Signing & Capabilities. Provisioning must support HealthKit. Camera and actual
   Health data still require hardware validation.

The project links the root Swift package at `../../..` relative to `apps/ios/App`.
After adding native files, `python3 scripts/generate_project.py` can regenerate the
project; it normalizes settings, so preserve any personal signing changes first.

## Tests and builds

Pure Python tests run on macOS/Linux without Xcode or the downloaded framework:

```sh
PYTHONPATH=core/python python3 -m unittest discover -s core/python/tests -v
```

On macOS, use a Python installation that includes matching headers and libpython
(`python3-config --embed --ldflags`), then run:

```sh
scripts/setup_python.sh
scripts/test.sh
```

`PYTHON_CONFIG=/path/to/python3-config scripts/test.sh` selects that installation.
The script sets the desktop interpreter home/module path and runs the Swift tests
through the **real C bridge and embedded interpreter**, without a subprocess proxy.
Direct `swift test` needs the same compiler/linker flags and environment; use the
script to avoid a mismatched Python library. The iOS runtime is independently pinned.

```sh
xcodebuild -project apps/ios/App/AITrainer.xcodeproj -scheme AITrainer \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath DerivedData \
  CODE_SIGNING_ALLOWED=NO ARCHS=arm64 build
scripts/smoke_ios.sh BOOTED_SIMULATOR_UUID
```

The Debug-only smoke mode uses an in-memory repository and checks onboarding,
workout evidence, progression/acceptance, nutrition and the offline catalog. It
writes `Documents/core-smoke-result.json` in the simulator app container and does
not alter saved athlete data. CI also builds Release and checks schema generation.

## Architecture and scope

Python now owns the deterministic Training Brain, double progression, initial plan
selection, workout/state transitions, proposal lifecycle, evidence re-evaluation,
correction/conflict rules, meal lifecycle, nutrient validation/scaling, descriptive
catalog validation and the explicit unassessed recovery boundary. Swift owns native
UI, sensors/perception, Codable DTOs, presentation projections and durable local saves.

The existing Swift feature-facing `TrainerService` delegates to
`LocalPythonTrainerService`. `TrainerCoreTransport.exchange(Data)` is the replaceable
boundary; a future remote transport can carry the same contracts without changing
feature/UI callers. Remote concurrency, authentication and offline synchronization
would still need implementation. Nothing currently switches to a network service.

- [Architecture and API extraction path](docs/LOCAL_PYTHON_ARCHITECTURE.md)
- [Migration, verification and limitations](docs/PYTHON_MIGRATION.md)
- [Open-source boundaries and licenses](docs/OPEN_SOURCE_INTEGRATION.md)
- [Physical-device checklist](docs/DEVICE_TEST_PLAN.md)
- [Original product specification](docs/AI_Trainer_01_Athlete_State_and_Training_Brain.md)

P0/P2 camera tools, P3 read-only HealthKit and P4 manual nutrition remain opt-in
experiments. Camera observations and catalog descriptions do not become confirmed
performance, reviewed guidance, or accepted recommendations automatically.
